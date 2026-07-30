import linecache

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


def make_src(*lines: str):
    return "\n".join(lines) + "\n"


def test_get_src_multiline(tmpdir):
    f = tmpdir.join("test.spy")
    src = make_src(
        "a",  # line 1
        "bb",  # line 2
        "ccc",  # line 3
    )
    f.write(src)
    loc = Loc(str(f), line_start=1, line_end=4, col_start=0, col_end=0)
    assert loc.get_src() == src
    #
    src = make_src(
        "def foo():",
        "....def inner():",  # line 2
        "        x = 1",
        "        y # hello",
        "    return innner",
    )
    #
    f.write(src)
    linecache.checkcache(str(f))
    loc = Loc(str(f), line_start=2, line_end=4, col_start=4, col_end=9)
    expected = make_src(
        "    def inner():",
        "        x = 1",
        "        y",
    )[:-1]  # remove the trailing newline
    assert loc.get_src() == expected
