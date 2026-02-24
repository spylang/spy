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
