from spy.location import Loc


def myfunc() -> Loc:
    loc = Loc.here()
    return loc


def test_Loc_here():
    loc = myfunc()
    src = loc.get_src()
    exp = "    loc = Loc.here()"
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
    exp = "    def foo():"
    assert src == exp
    #
    loc = Loc.from_pyfunc(bar)
    src = loc.get_src()
    exp = "    def bar():"


def test_get_src_multiline():
    loc = Loc.here()
    # 1234567890ABCD
    #
    # make a new loc which spans two lines
    loc2 = loc.replace(line_end=loc.line_end + 1)
    exp = """\
    loc = Loc.here()
    # 1234567890ABCD
    """[:-5]  # remove the last line
    assert loc2.get_src() == exp
