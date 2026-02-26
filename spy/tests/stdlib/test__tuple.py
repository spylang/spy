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

    def test_len(self):
        mod = self.compile("""
        from _tuple import tuple

        def foo() -> i32:
            tup = tuple[int, int, str](1, 2, 'hello')
            return len(tup)
        """)
        x = mod.foo()
        assert x == 3

    def test_eq(self):
        mod = self.compile("""
        def tup1() -> tuple[int, int]:
            return 1, 2

        def tup2() -> tuple[int, int]:
            return 3, 4

        def foo() -> bool:
            return tup1() == tup1()

        def bar() -> bool:
            return tup1() == tup2()
        """)
        assert mod.foo()
        assert not mod.bar()
