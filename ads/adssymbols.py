# Copyright (c) 2018, DEMCON advanced mechatronics
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
# 
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# 
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


from . import cpyads
from .nonzerobasedarray import NonzeroBasedArray
from ctypes import *
from collections import OrderedDict, namedtuple
import re
import itertools
import warnings
import struct



ADSIGRP_SYM_HNDBYNAME = 0xF003
ADSIGRP_SYM_VALBYHND = 0xF005
ADSIGRP_SYM_UPLOADINFO = 0xF00C
ADSIGRP_SYM_UPLOAD = 0xF00B
ADSIGRP_SYM_UPLOADINFO2	= 0xF00F
ADSIGRP_SYM_DT_UPLOAD = 0xF00E


class Dummy(Array):
    """
    Helper class to reduce chance of accidental writing to dummy ctypes objects
    
    objects could still be accidentally written as part of another ctypes
    object
    """
    _length_ = 1
    _type_ = c_ubyte
    def __init__(self, *args):
        raise RuntimeError('Dummy ctypes object cannot be created or written')

class Entry:
    """
    Using ADS calls, two data blobs containing information on the symbols and
    the data types of the currently active PLC program can be read. The Entry
    class is the base of the AdsSymbolEntry and the AdsDatypeEntry classes 
    which represent the entries that are stored in these two blobs.
    
    The data for an Entry consists of a number of fields in a fixed structure,
    followed by fields of variable lengths (e.g. the name of the entry). The
    data in the fixed structure is used to determine the lengths of these
    variable fields.
    
    """
    
    _fields = []
    _fieldsformat = ''
    
    def _parsefields(self, data):
        """
        Parse the fields in the fixed structure using self._fields and 
        self._fieldsformat. The resulting data is stored as members of this
        object
        
        """
        formatlength = struct.calcsize(self._fieldsformat)
        
        for fieldname, value in zip(self._fields, struct.unpack(self._fieldsformat, data[:formatlength])):
            setattr(self, fieldname, value)
        
        return data[formatlength:]
    
    @staticmethod
    def _field(length, data):
        """
        Split data at position given by length. Returns a tuple of (the first
        length bytes, the remainder)
        """
        return data[:length], data[length:]
    
    @staticmethod
    def _stringfield(length, data):
        """
        Split data as a string of given length. The first length bytes are the
        string, then a NUL which is ignored, then the remainder. Returns a tuple
        of (the first length bytes decoded as string, the remainder)
        """
        
        return data[:length].decode('latin-1'), data[length+1:]
        
    @classmethod
    def iter(cls, data):
        """
        Iterate over entries of this class sourced from a blob of binary data
        """
        
        p = 0
        while p<len(data):
            # The first 4 bytes of each entry are always its length
            length, = struct.unpack('L', data[p:p+4])
            
            # Create an object of our class from the data
            yield cls(data[p:p+length])
            p+=length
        
class AdsDatatypeEntry(Entry):
    """
    Class represinging an ADS data type
    """
        
    _fields = [
        'entryLength', 'version', 'hashValue', 'typeHashValue', 'size', 'offs',
        'dataType', 'flags', 'nameLength', 'typeLength', 'commentLength',
        'arrayDim', 'subItemsCount'
        ]
    _fieldsformat = 'LLLLLLLLHHHHH'

    def __init__(self, data):
        # Parse fixed structure
        remainder = self._parsefields(data)

        # Parse string fields
        self.name, remainder = self._stringfield(self.nameLength, remainder)
        self.type, remainder = self._stringfield(self.typeLength, remainder)
        self.comment, remainder = self._stringfield(self.commentLength, remainder)
        
        # Parse the dimensions of the array
        dims = [] # List of tuples (lBound, elements)
        for i in range(self.arrayDim):
            dim, remainder = self._field(8, remainder)
            # Note: lbound is unsigned according to TcAdsDef.h, but in fact
            # lbound can be negative so it needs to be signed
            dims.append(struct.unpack('lL', dim))
        
        self.array = dims

        # Parse the subitems
        subItems = OrderedDict()
        
        for i in range(self.subItemsCount):
            length, = struct.unpack('L', remainder[:4])
            
            subItemData, remainder = self._field(length, remainder)
            subItem = AdsDatatypeEntry(subItemData)
            subItems[subItem.name] = subItem
         
        self.subItems = subItems
        


    def __repr__(self):
        ar = ','.join('%d..%d' % (d[0], d[0] + d[1]-1) for d in self.array)
        r = '\n%r %r [%s]' % (self.name, self.type, ar)
        for i in self.subItems.values():
            for l in repr(i).strip('\n').split('\n'):
                r+='\n  ' + l
        return r+'\n'
        
        
        
        

class AdsSymbolEntry(Entry):
    """
    Class representing a symbol in the PLC program 
    """
    _fields = [
        'entryLength', 'iGroup', 'iOffs', 'size', 'dataType', 'flags',
        'nameLength', 'typeLength', 'commentLength'
        ]
    _fieldsformat = 'LLLLLLHHH'
    
    def __init__(self, data):
        
        remainder = self._parsefields(data)

        self.name, remainder = self._stringfield(self.nameLength, remainder)
        self.type, remainder = self._stringfield(self.typeLength, remainder)
        self.comment, remainder = self._stringfield(self.commentLength, remainder)


basictypes = { 
    'BOOL' : c_bool,
    'BIT' : c_bool,
    'BYTE' : c_byte,
    'DATE' : c_int32,
    'DINT' : c_int32,
    'DT' : c_int32,
    'DWORD' : c_int32,
    'INT' : c_int16,
    'LREAL' : c_double,
    'REAL' : c_float,
    'SINT' : c_int8,
    'STRING' : c_char,
    'TIME' : c_int32,
    'TOD' : c_int32,
    'UDINT' : c_uint32,
    'UINT' : c_uint16,
    'USINT' : c_uint8,
    'WORD' : c_int16,
    'LINT': c_int64,
    'ULINT': c_uint64,
    'PVOID': c_void_p,
    'OTCID': c_int32,
}
                 
class PLCString(Structure):
    """
    PLCString represents a PLC string. Create a PLC string of size n using
    the static method PLCString.create(n)
    
    """
    @staticmethod
    def create(length):
        return type('STRING(%d)' % length , (PLCString,), dict(_fields_ = [('data', c_char * (length + 1))]))

    def __init__(self, str = ''):
        super().__init__(str.encode('latin-1') + b'\0') #Add terminating 0
        
    def __repr__(self):
        return self.data.decode('latin-1')


VariableInfo = namedtuple('VariableInfo', 'name symbol offset datatype ctype variablesDefinition')

class Variable:
    """
    Represents a variable (of either simple or structured/array data type)
    within the PLC program. The following operations are defined on a variable:
    
    attribute access var.attr
      retrieve a sub-variable of a structured datatype
    
    indexing var[i]
      retrieve an item from an array
      
    calling without arguments var()
      read the variable from the PLC
      
    calling with arguments var(value)
      write the variable to the PLC
    
    negation ~var
      retrieve auxiliary data (e.g. name, symbol object, datatype etc)
    
    
    """
    
    
    
    def __init__(self, vardef, name, symbol, datatype, offset):
        """
        vardef: the AdsVariablesDefinition object to which this variable belongs
        name: name of this variable
        ads: ads address
        symbol: AdsSymbolEntry representing the symbol to which this variable
          belongs
        datatype: either
          - string: will be looked up in PLC (custom) types list contained in
            vardef.dtypes
          - AdsDatatypeEntry
        offset: offset (in bytes) of this variable with respect to the 
            start of the symbol
        """
        self.__name = name
        self.__vardef = vardef
        self.__symbol = symbol
        self.__ctype = None
        self.__datatype = None
        
            
        if not isinstance(datatype, str):
            # Datatype specified as AdsDatatypeEntry
            self.__datatype = datatype
            
        else:
            # datatype is a string
            
            # Check if we know this datatype as a custom datatype
            self.__datatype = self.__vardef.dtypes.get(datatype)
            
            if self.__datatype is not None:
                # We have found a datatype
                if (self.__datatype.type != '' and not self.__datatype.array
                    and not self.__datatype.subItems 
                    and not self.__datatype.name.startswith('POINTER TO ')):
                        
                    # self.__datatype is an alias e.g. enum, look it up below
                    datatype = self.__datatype.type
                    self.__datatype = None
                    
            if self.__datatype is None:
                # We have not found the original datatype in our custom datatypes
                # or it we have found a custom datatype which is an alias (e.g. enum)
                self.__ctype = basictypes.get(datatype)
                
                if self.__ctype is None:
                    stringMatch = re.match(r'STRING\((\d+)\)', datatype)
                    if stringMatch is not None:
                        # Create a PLCString type for the given length
                        stringLength = int(stringMatch.group(1))
                        self.__ctype = PLCString.create(stringLength)
                        
                    else:
                        # Unknown datatype
                        warnings.warn('Unknown datatype: %s' % datatype)

                
        # __datatype will be None for unknown and basic types
        if self.__datatype is not None and self.__ctype is None:
            # See if we can find a ctype for this variable, so it an be read/written
            self.__ctype = self.__vardef.getCtype(self.__datatype.name)

        
        self.__offset = offset
        if offset is None:
            self.__offset = 0

    def __invert__(self):
        """ 
        The ~ operator overload is 'abused' to get auxiliary data from this
        variable.
        
        It returns a VariableInfo object
        
        """
        
        return VariableInfo(
                name = self.__name,
                symbol = self.__symbol,
                offset = self.__offset,
                datatype = self.__datatype,
                ctype = self.__ctype,
                variablesDefinition = self.__vardef,
            )

    def __dir__(self):
        """
        Build a list of all possible attributes from the subitems of our datatype
        This enables the use of the dir() function and tab-completion
        """
        if self.__datatype is None:
            return []
            
        return self.__datatype.subItems.keys()
    
    def __getattr__(self, name):
        """
        If this variable is a structured data type, get one of the fields
        """
        if self.__datatype is None:
            raise AttributeError('Variable has no attributes')
            
        try:
            type = self.__datatype.subItems[name]
            
        except KeyError:
            raise AttributeError('Variable has no attribute %s' % name)

        offset = type.offs + self.__offset
        
        if type.type:
            type = type.type

        return Variable(self.__vardef, name, self.__symbol, type, offset)
    
    
    def __iter__(self):
        """
        Iterate over the variable. 
        
        In case of an array, iterate over all items in it (in case of
        a multidimensional array, iterates over all items in all
        dimensions e.g.[0,0] [0,1] [1,0] [1,1]. Yields pairs of (index as string,
        variable)
        
        In case of a structured datatype, iterate over all fields. Yields pairs
        of (fieldName, variable)
        """
        if self.__datatype is None:
            raise TypeError('Variable is not iterable')
            
        if self.__datatype.array:
            # Iterate linearly over the array
            dims = [range(a[0], a[0] + a[1]) for a in self.__datatype.array]
            for idx in itertools.product(*dims):
                idxStr = '[%s]' % ','.join(str(i) for i in idx)
                yield idxStr, self[idx]
            

        elif self.__datatype.subItems:
            # Iterate over the subItems
            for subItemName in self.__datatype.subItems.keys():
                yield subItemName, getattr(self, subItemName)
                
            
            
    def __len__(self):
        """
        Returns the number of sub-items in case of an array variable (the
        product of the dimensions)
        
        Raises TypeError in case the variable is not an array
        """        
        if self.__datatype is None or not self.__datatype.array:
            raise TypeError('Variable is not an array datatype')
        
        length = 1
        for lower, elements in self.__datatype.array:
            length = length * elements
        
        return length
    
    def __getitem__(self, idx):
        """
        Index an item in case this variable is an array
        
        Multidimensional arrays are indexed as var[1,3] not var[1][3]
        
        Slice-based indexing can also be used to read out the raw binary data
        """
        
        if isinstance(idx, slice) and self.__datatype is not None:
            # Slice based indexing --> read out raw data
            start, stop, step = idx.indices(self.__datatype.size)
            if step!=1:
                raise ValueError('Step size should be 1')
            
            data = cpyads.adsSyncReadReq(self.__vardef.amsAddress, self.__symbol.iGroup, self.__symbol.iOffs + self.__offset + start, cpyads.c_ubyte * (stop-start))
            return data
            
        if self.__datatype is None or len(self.__datatype.array) == 0:
            raise IndexError('Variable cannot be indexed')
            
        if not isinstance(idx, tuple):
            idx = idx,
            
        if len(idx) != len(self.__datatype.array):
            raise IndexError(
                'Incorrect number of dimensions. %s has %d but %d given' 
                % (self.__datatype.name, len(self.__datatype.array), len(idx)))
        
        # Compute the linear index in the array and the number of elements in the array
        linearIndex = 0
        nItems = 1
        for i, (lower, elements) in zip(idx, self.__datatype.array):
            if i<lower or i >= lower+elements:
                raise IndexError('Index out of range')

            linearIndex *= elements
            linearIndex += i-lower
            nItems *= elements
        
        assert (self.__datatype.size % nItems) == 0
        elementSize = self.__datatype.size // nItems
        
        type = self.__datatype.type
        if not type:
            # Not even sure if this exists within ADS/TwinCAT
            raise NotImplementedError('Arrays of custom types not implemented')
        
        # Compute the offset of the variable in bytes
        offset = self.__offset + linearIndex * elementSize
        
        # Compose the index as string
        idxStr = '[%s]' % ','.join(str(i) for i in idx)
        
        return Variable(self.__vardef, idxStr, self.__symbol, type, offset)

    def __setitem__(self, idx, data):
        """

        Slice-based indexing can be used to write the raw binary data
        """
        
        assert isinstance(idx, slice) and self.__datatype is not None
        # Slice based indexing --> write raw data
        start, stop, step = idx.indices(self.__datatype.size)
        if step!=1:
            raise ValueError('Step size should be 1')

        view = memoryview(data)
        # Quirck to get a ctypes object which maps to the memoryview, see 
        # https://lists.gt.net/python/dev/1011232
        address = c_void_p()
        length = c_ssize_t()
        pythonapi.PyObject_AsReadBuffer(py_object(view), byref(address), byref(length))
        
        if stop-start != length.value:
            raise ValueError('data length does not match slice size')
        
        cbyte_array = (c_ubyte * length.value).from_address(address.value)
        
        cpyads.adsSyncWriteReq(self.__vardef.amsAddress, self.__symbol.iGroup, self.__symbol.iOffs + self.__offset + start, cbyte_array)
    

    def __call__(self, *args, **kwargs):
        """
        Read or write a variable from/to the PLC by calling
        
        Call without arguments to perform a read. Returns a ctypes object when
        it is an array or struct, or the actual value when it is a simple variable
        
        For writing, if there is a single argument which is of the ctypes class
        that corresponds to this variable, that is written to the PLC variable.
        In all other cases, the arguments to the call are passed to the ctypes
        class constructor.
        
        
        """
        if len(args)==0 and len(kwargs) == 0:
            # Read
            assert self.__ctype is not None
            data = cpyads.adsSyncReadReq(self.__vardef.amsAddress, self.__symbol.iGroup, self.__symbol.iOffs + self.__offset, self.__ctype)
            
            if issubclass(self.__ctype, PLCString):
                data = str(data)
            elif not issubclass(self.__ctype, (Array, Structure)):
                data = data.value
            return data   
            
        else:
            # Write
            assert self.__ctype is not None
            if len(args) == 1 and len(kwargs)==0 and isinstance(args[0], self.__ctype):
                # We have exactly one argument, which is of the correct type
                data = args[0]
            else:
                # Not exactly one argument or not of the correct type. Try to make
                # it into the correct type using the ctype class constructor
                data = self.__ctype(*args, **kwargs)
            cpyads.adsSyncWriteReq(self.__vardef.amsAddress, self.__symbol.iGroup, self.__symbol.iOffs + self.__offset, data)
                

    def __repr__(self):
        if self.__ctype is not None:
            return '<Variable %s = %r>' % (self.__name, self())
        elif self.__datatype is not None:
            return '<Variable %s of type %s>' % (self.__name, self.__datatype.name)
        else:
            return '<Variable (unknown type)>'
            
            
class Variables():
    def __iter__(self):
        return iter(self.__dict__.items())

class AdsVariablesDefinition():
    def __init__(self, address):
        self.dtypes = {}
        self.ctypes = basictypes.copy()
        self.amsAddress = address

        # Get symbol upload info; read symbol info and data types
        symbolUploadInfo = cpyads.adsSyncReadReq(address, ADSIGRP_SYM_UPLOADINFO2, 0, c_ulong * 6)
        
        nSymbols, nSymSize, nDatatypes, nDatatypeSize, nMaxDynSymbols, nUsedDynSymbols = symbolUploadInfo
        
        symbolsData = cpyads.adsSyncReadReq(address, ADSIGRP_SYM_UPLOAD, 0, c_char * nSymSize)
        datatypesData = cpyads.adsSyncReadReq(address, ADSIGRP_SYM_DT_UPLOAD, 0, c_char * nDatatypeSize)
        
        # Create a mapping of name -> PLC AdsDataType
        self.dtypes = {t.name: t for t in AdsDatatypeEntry.iter(datatypesData)}
        
        # Create Ctypes classes for all PLC AdsDataTypes
        for dtypename in self.dtypes.keys():
            self.getCtype(dtypename)
        
        # Get a list of symbols
        symbols = list(AdsSymbolEntry.iter(symbolsData))

        vars = Variables()
        
        for symbol in symbols:
        
            # if symbol.type not in self.dtypes and symbol.type not in basictypes:
            #     print(symbol.type, '!!', symbol.name, symbol.comment)
            
            rest = symbol.name
            parent = vars
            while True:
                name, dot, rest = rest.partition('.')
                if rest == '':
                    break
        
                try:
                    parent = getattr(parent, name)
                except AttributeError:
                    child = Variables()
                    setattr(parent, name, child)
                    parent = child
        
                
            setattr(parent, name, Variable(self, name, symbol, symbol.type, 0))
        
        self.variables = vars
 
    def getCtype(self, dtypename, size = None):
        if dtypename in self.ctypes:
            return self.ctypes[dtypename]
        
        
        stringMatch = re.match(r'STRING\((\d+)\)', dtypename)
        if stringMatch is not None:
            # Create a PLCString type for the given length
            stringLength = int(stringMatch.group(1))
            ctype = PLCString.create(stringLength)
        else:
            fields = []
            
        
            dtype = self.dtypes.get(dtypename, None)
            if dtype is None:
                # if we do not know the type, but we know the size (if we have a 
                # recursive call), create a dummy type
                if size is None:
                    warnings.warn('Unknown type %s with unknown size' % dtypename)
                    return None
                warnings.warn('Unknown type %s with known size, replaced with dummy ctype of %d bytes' % (dtypename, size))
                return type('Dummy', (Dummy,), dict(_length_ = size))
                
            
            if dtype.name.startswith('POINTER TO '):
                ctype = c_void_p
            elif dtype.type and not dtype.subItems:
                # determine the expected size of each of the array items
                # this is required in case we have an array of items of an unknown type
                arraysize = 1
                for lbound, elements in dtype.array:
                    arraysize *= elements
                itemsize, remainder = divmod(dtype.size, arraysize)
                assert remainder == 0
                
                
                ctype = self.getCtype(dtype.type, itemsize)
                assert ctype is not None
                
            elif dtype.subItems and not dtype.type:
                o = 0
                for s in dtype.subItems.values():
                    if s.offs > o:
                        # Add dummy field with empty name to fill space
                        fields.append(('', c_char * (s.offs-o)))
                        o = s.offs
                    if s.offs == o:
                        fields.append((s.name, self.getCtype(s.type, s.size)))
                        o += s.size
                    else:
                        warnings.warn('union not yet supported')
                        pass
                        
                
                if o < dtype.size:
                    # Add dummy field with empty name to fill space
                    fields.append(('', c_char * (dtype.size-o)))
            
                ctype = type(dtype.name, (Structure,), dict(_fields_ = fields, _pack_ = 8))
                
            else:
                warnings.warn('Unknown type %s with known size, replaced with dummy ctype of %d bytes' % (dtypename, dtype.size))
                ctype = c_char * dtype.size
            
        
            
            for lbound, elements in reversed(dtype.array):
                if lbound == 0:
                    # Array index starts at 0, this is the same as standard ctype
                    ctype = elements * ctype
                else:
                    # Array index does not start at 0, use a custom class
                    ctype = NonzeroBasedArray.create(ctype, lbound, elements)
            
        
            if dtype.size != sizeof(ctype):
                warnings.warn('Ctype size of datatype %s does not match, replaced with dummy ctype of %d bytes' % (dtype.name, dtype.size))
                ctype = type('Dummy', (Dummy,), dict(_length_ = dtype.size))
 
    
        self.ctypes[dtypename] = ctype
        return ctype        
 
def getVariables(netId = None, port = 851):
    cpyads.adsPortOpen()
    
    addr = cpyads.SAmsAddr(netId, port)
    
    return AdsVariablesDefinition(addr).variables
    
    

