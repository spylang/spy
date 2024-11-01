from spy.location import Loc
from spy.errors import Annotation

def myfunc() -> Loc:
    loc = Loc.here()
    return loc

def test_Loc_here():
    loc = myfunc()
    ann = Annotation("error", "hello", loc)
    src = ann.get_src()
    exp = '    loc = Loc.here()'
    assert src == exp
