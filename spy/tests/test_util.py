from typing import Any
import pytest
from spy.util import magic_dispatch

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
