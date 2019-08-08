
import ctypes
from ads.nonzerobasedarray import NonzeroBasedArray


def test_usage():
    T1 = NonzeroBasedArray.create(ctypes.c_byte, -2, 4)
    T2 = NonzeroBasedArray.create(ctypes.c_byte*4, -2, 4)

    t1=T1(*[5,6,7,7])
    t2=T2()
    assert (ctypes.addressof(t2[-1]) - ctypes.addressof(t2)) == 4
    for i, v in enumerate(t2[-2:2]):
        assert (ctypes.addressof(v) - ctypes.addressof(t2))== i*4
    
    t1[-1] = 4
    assert t1[-1] == 4
