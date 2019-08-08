
from ads import adssymbols


def test_plc_string():
    s = adssymbols.PLCString.create(25)
    print(s)
