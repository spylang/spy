from spy.location import Loc
from spy.errors import Annotation

def get_src(loc: Loc) -> str:
    ann = Annotation("error", "hello", loc)
    return ann.get_src()

def myfunc() -> Loc:
    loc = Loc.here()
    return loc

def test_Loc_here():
    loc = myfunc()
    src = get_src(loc)
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
    src = get_src(loc)
    exp = '    def foo():'
    assert src == exp
    #
    loc = Loc.from_pyfunc(bar)
    src = get_src(loc)
    exp = '    def bar():'
