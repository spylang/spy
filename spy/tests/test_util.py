from typing import Any
import pytest
from spy.util import ANYTHING, magic_dispatch, extend, shortrepr, func_equals

def test_ANYTHING():
    assert ANYTHING == 1
    assert 1 == ANYTHING
    assert ANYTHING == ANYTHING
    assert not ANYTHING != 1
    assert not 1 != ANYTHING
    assert not ANYTHING != ANYTHING

def test_magic_dispatch():
    class Foo:
        def visit(self, obj: Any, arg: int) -> Any:
            return magic_dispatch(self, 'visit', obj, arg)

        def visit_int(self, x: int, y: int) -> int:
            return x + y

        def visit_str(self, s: str, n: int) -> str:
            return s.upper() * n

    f = Foo()
    assert f.visit(4, 5) == 9
    assert f.visit('bar-', 3) == 'BAR-BAR-BAR-'
    with pytest.raises(NotImplementedError, match='visit_float'):
        f.visit(1.0, -1)

def test_magic_dispatch_NotImplemented():
    class Foo:
        def visit(self, obj: Any, arg: int) -> Any:
            return magic_dispatch(self, 'visit', obj, arg)

        def visit_int(self, x: int, y: int) -> int:
            return x + y

        def visit_NotImplemented(self, obj: Any, arg: int) -> Any:
            return f'hello NotImplemented {obj} {arg}'

    f = Foo()
    assert f.visit(4, 5) == 9
    assert f.visit('world', 42) == 'hello NotImplemented world 42'


def test_extend():
    class Foo:
        pass

    @extend(Foo)
    class Foo2:
        X = 100

        def meth(self):
            return 42

    assert Foo2 is Foo
    assert Foo.X == 100        # type: ignore
    assert Foo().meth() == 42  # type: ignore

def test_extend_dont_overwrite():
    class Foo:
        X = 42

    with pytest.raises(TypeError, match="class Foo has already a member 'X'"):
        @extend(Foo)
        class Foo2:
            X = 100


def test_shortrepr():
    s = '12345678'
    assert shortrepr(s, 10) == "'12345678'"
    assert shortrepr(s,  8) == "'12345678'"
    assert shortrepr(s,  7) == "'12345...'"


# ======= tests for same_closure =======

class Test_func_equals:

    def test_identity(self):
        def f():
            pass
        assert func_equals(f, f)

    def test_different_code_objects(self):
        def f(): pass
        def g(): pass
        assert not func_equals(f, g)

    def test_no_defaults(self):
        def make(n):
            def fn(x=n):
                pass
            return fn
        f0 = make(0)
        f1 = make(1)
        with pytest.raises(ValueError, match="unsupported: default arguments"):
            func_equals(f0, f1)

    def test_no_kwdefaults(self):
        def make(n):
            def fn(*, x=n):
                pass
            return fn
        f0 = make(0)
        f1 = make(1)
        with pytest.raises(ValueError,
                           match="unsupported: kwargs with default arguments"):
            func_equals(f0, f1)

    def test_closure(self):
        def make(n):
            def fn():
                return n
            return fn
        f0 = make(0)
        f1 = make(1)
        f0b = make(0)
        assert not func_equals(f0, f1)
        assert func_equals(f0, f0b)
