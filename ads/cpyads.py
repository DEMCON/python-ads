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


from ctypes import (
    c_byte, c_ubyte, c_short, c_ushort, c_long, c_ulong, c_void_p,
    byref, sizeof, POINTER, CDLL, Structure
    )




class SAdsVersion(Structure):
    _fields_=[("version", c_byte),
             ("revision", c_byte),
             ("build", c_short)]   
             
class SAmsAddr(Structure):
    _fields_ = [("netId", c_ubyte * 6),
                ("port", c_ushort)]
    
    def __init__(self, netId = None, port = None):
        '''
        Structure representing an Ams Address
        
        if netId is None, it is set to the local address
    
        if port is None and netId is None, the port is set to the port of the
          local address
          
        if netId is not None, the port must be specified (it cannot be none)
        '''
        
        if netId is not None:
            # Convert string x.x.x.x.x.x to tuple of ints
            self.netId[:] = tuple(map(int, netId.split('.')))
            self.port = port
        else:
            # Default to local address
            AdsDll.lib().AdsGetLocalAddress(byref(self))
            
            # Allow overriding port
            if port is not None:
                self.port = port
    
    def __repr__(self):
        return '%s:%d' % ('.'.join(map(str, self.netId)), self.port)

def checkError(error):
    if error != 0:
        raise IOError('Error ' + str(error))

class AdsDll:
    _lib = None
    
    @classmethod
    def lib(cls):
        if cls._lib is None:
            

            lib = CDLL("AdsDll.dll")
            lib.AdsPortOpen.restype = c_long
            lib.AdsPortOpen.argtypes = []
            
            for function, argtypes in [
                (lib.AdsPortClose, []),
                (lib.AdsGetLocalAddress, [POINTER(SAmsAddr)]),
                (lib.AdsSyncReadReq, [POINTER(SAmsAddr), c_ulong, c_ulong, c_ulong, c_void_p]),
                (lib.AdsSyncWriteReq, [POINTER(SAmsAddr), c_ulong, c_ulong, c_ulong, c_void_p]),
                (lib.AdsSyncWriteControlReq, [POINTER(SAmsAddr), c_ushort, c_ushort, c_ulong, c_void_p]),
                (lib.AdsSyncReadStateReq, [POINTER(SAmsAddr), POINTER(c_ushort), POINTER(c_ushort)])
            ]:
                
                function.argtypes = argtypes
                function.restype = checkError
        
            cls._lib = lib
        return cls._lib

def adsPortOpen():
    return AdsDll.lib().AdsPortOpen()

def adsGetLocalAddress():
    return SAmsAddr()

def adsSyncReadReq(amsAddr, indexGroup, indexOffset, ctype):
    data = ctype() # Create object to be read into
    AdsDll.lib().AdsSyncReadReq(byref(amsAddr), indexGroup, indexOffset, sizeof(data), byref(data))    
    return data

def adsSyncWriteReq(amsAddr, indexGroup, indexOffset, data):
    AdsDll.lib().AdsSyncWriteReq(byref(amsAddr), indexGroup, indexOffset, sizeof(data), byref(data))

def adsGetAdsAndDeviceState(amsAddr):
    ads_state = c_ushort(0)
    device_state = c_ushort(0)
    AdsDll.lib().AdsSyncReadStateReq(byref(amsAddr), byref(c_ushort(0)), byref(device_state))
    return ads_state, device_state

def adsStop(amsAddr):
    ads_state, device_state = adsGetAdsAndDeviceState(amsAddr)  # Retrieve device state so we don't alter it next
    AdsDll.lib().AdsSyncWriteControlReq(byref(amsAddr), c_ushort(6), device_state, 0, c_void_p())

def adsReset(amsAddr):
    ads_state, device_state = adsGetAdsAndDeviceState(amsAddr)  # Retrieve device state so we don't alter it next
    AdsDll.lib().AdsSyncWriteControlReq(byref(amsAddr), c_ushort(2), device_state, 0, c_void_p())

def adsStart(amsAddr):
    ads_state, device_state = adsGetAdsAndDeviceState(amsAddr)  # Retrieve device state so we don't alter it next
    AdsDll.lib().AdsSyncWriteControlReq(byref(amsAddr), c_ushort(5), device_state, 0, c_void_p())

def adsRestart(amsAddr):
    # Stopping ads can throw an exception if it was not currently running but we can reset anyway
    try:
        adsStop(amsAddr)
    except:
        pass
    adsReset(amsAddr)
    adsStart(amsAddr)

__all__ = [ 'adsPortOpen', 'adsGetLocalAddress', 'adsSyncReadReq' ]
    
