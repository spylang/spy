from spy.location import Loc
from spy.errors import Annotation

def myfunc() -> Loc:
    loc = Loc.here()
    return loc

def test_Loc_here():
    loc = myfunc()
    src = loc.get_src()
    exp = '    loc = Loc.here()'
    assert src == exp

def test_Loc_from_pyfunc():
    def decorator(fn):
        return fn

    def foo():
        pass

    @decorator
    def bar():
        pass

    loc = Loc.from_pyfunc(foo)
    src = loc.get_src()
    exp = '    def foo():'
    assert src == exp
    #
    loc = Loc.from_pyfunc(bar)
    src = loc.get_src()
    exp = '    def bar():'
