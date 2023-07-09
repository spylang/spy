from typing import Any
import pytest
from spy.util import ANYTHING, magic_dispatch, extend

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
