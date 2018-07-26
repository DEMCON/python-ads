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


# Ctypes non-zero-based array
import ctypes

class NonzeroBasedArray:
    """
    This class is a support for PLC arrays, which do not necessarily start at
    index 0.

    The lower bound of a PLC array can even be negative. To avoid ambiguity,
    a PLC array cannot be indexed 'counted from the back' i.e. a[-1] will not
    be interpreted as 'the last item' but instead as item -1 (assuming -1 is
    a valid index; otherwise, an IndexError will be raised)
    """
    
    @classmethod
    def create(cls, ctype, lbound, length):
        typename = '%s_Array_%d_to_%d' % (ctype.__name__, lbound, lbound+length-1)
        d = dict(_length_ = length, _type_ = ctype, _lbound_ = lbound)
        return type(
            typename, 
            (cls, ctypes.Array), 
            d)
    
    
    def __init__(self, *args):
        super().__init__()
        
        for i, v in enumerate(args):
            self[i + self._lbound_] = v
    
    def __getitem__(self, index):
        return super().__getitem__(self.__convertindex__(index))

    def __setitem__(self, index, value):
        return super().__setitem__(self.__convertindex__(index), value)

    def __convertindex__(self, index):
        if isinstance(index, int):
            index = index - self._lbound_
            if index < 0:
                raise IndexError('invalid index')
                # Start too high will be caught by super
            
        elif isinstance(index, slice):
            start, stop, step = index.start, index.stop, index.step
            
            if start is not None:
                start = start - self._lbound_
                if start < 0:
                    raise IndexError('invalid index')
                # Start too high will be caught by super
            
            if stop is not None:
                stop = stop - self._lbound_
                if stop < 0:
                    raise IndexError('invalid index')
                # End too high will be caught by super
            index = slice(start, stop, step)
        else:
            raise TypeError('indices must be integers')
        return index
        
        
    def __iter__(self):
        '''
        Iterate over the array
        '''
        i = self._lbound_
        while True:
            try:
                yield self[i]
            except IndexError:
                raise StopIteration
            i += 1
   
if __name__ == '__main__':
        
    T1 = NonzeroBasedArray.create(ctypes.c_byte, -2, 4)
    T2 = NonzeroBasedArray.create(ctypes.c_byte*4, -2, 4)

    t1=T1(*[5,6,7,7])
    t2=T2()
    assert (ctypes.addressof(t2[-1]) - ctypes.addressof(t2)) == 4
    for i, v in enumerate(t2[-2:2]):
        assert (ctypes.addressof(v) - ctypes.addressof(t2))== i*4
    
    t1[-1] = 4
    assert t1[-1] == 4