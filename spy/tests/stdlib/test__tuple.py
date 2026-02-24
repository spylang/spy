import pytest

from spy.tests.support import CompilerTest


class TestTange(CompilerTest):
    def test_simple(self):
        src = """
        from _tuple import tuple

        def make_pair(a: str, b: i32) -> tuple[str, i32]:
            return tuple[str, i32](a, b)
        """
        mod = self.compile(src)
        p = mod.make_pair("hello", 42)
        assert p == ("hello", 42)
        assert p._item0 == "hello"
        assert p._item1 == 42

    def test_getitem(self):
        src = """
        from _tuple import tuple

        def foo(x: i32, y: i32) -> i32:
            t = tuple[int, int](x, y)
            return t[1]
        """
        mod = self.compile(src)
        res = mod.foo(10, 20)
        assert res == 20
