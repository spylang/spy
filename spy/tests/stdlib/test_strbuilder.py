import textwrap

import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest
from spy.util import print_diff


@pytest.fixture(params=["StrBuilder", "Unsafe"])
def Builder(request):
    if request.param == "StrBuilder":
        return "StrBuilder"
    elif request.param == "Unsafe":
        return "UnsafeFixedStrBuilder"
    else:
        assert False


class TestStrBuilder(CompilerTest):
    def assert_dump(self, got: str, expected: str) -> None:
        expected = textwrap.dedent(expected).strip()
        if got != expected:
            print_diff(expected, got, "expected", "got")
            pytest.fail("assert_dump failed")

    def test_append(self, Builder):
        src = f"""
        from strbuilder import {Builder} as SB

        def concat(cap: int, a: str, b: str, c: str) -> str:
            sb = SB(cap)
            sb.append(a)
            sb.append(b)
            sb.append(c)
            return sb.build()
        """
        mod = self.compile(src)
        assert mod.concat(0, "", "", "") == ""
        assert mod.concat(5, "", "hello", "") == "hello"
        assert mod.concat(7, "abc", "def", "!") == "abcdef!"
        assert mod.concat(7, "é", "🐍", "!") == "é🐍!"
        assert mod.concat(4, "a\x00", "b", "\x00") == "a\x00b\x00"
        # underfill: we leak some memory but the string is valid
        assert mod.concat(10, "ab", "cd", "e") == "abcde"

    def test_append_growing(self):
        src = f"""
        from strbuilder import StrBuilder, dump_builder

        def concat(cap: int, a: str, b: str, c: str) -> tuple[str, str]:
            sb = StrBuilder(cap)
            sb.append(a)
            sb.append(b)
            sb.append(c)
            dump = dump_builder(sb)
            return sb.build(), dump
        """
        mod = self.compile(src)
        # chunk is full -> grow
        s, dump = mod.concat(5, "hello", " ", "world")
        assert s == "hello world"
        expected = """
        [unsealed] pos=6     cap=10    " world...."
        [sealed  ] pos=5     cap=5     "hello"
        """
        self.assert_dump(dump, expected)

        # chunk is not full but it's not big enough: fill + grow + copy rest
        s, dump = mod.concat(8, "hello", " ", "world")
        assert s == "hello world"
        expected = """
        [unsealed] pos=3     cap=16    "rld............."
        [sealed  ] pos=8     cap=8     "hello wo"
        """
        self.assert_dump(dump, expected)

    def test_append_slice(self, Builder):
        src = f"""
        from strbuilder import {Builder} as SB

        def slice_of(cap: int, chunk: str, start: int, end: int) -> str:
            sb = SB(cap)
            sb.append_slice(chunk, start, end)
            return sb.build()
        """
        mod = self.compile(src)
        # prefix, middle, suffix
        assert mod.slice_of(3, "world", 0, 3) == "wor"
        assert mod.slice_of(3, "world", 1, 4) == "orl"
        assert mod.slice_of(2, "world", 3, 5) == "ld"
        # empty slice, empty source
        assert mod.slice_of(0, "abc", 1, 1) == ""
        assert mod.slice_of(0, "", 0, 0) == ""
        # UTF-8: "é" is 2 bytes, "🐍" is 4
        assert mod.slice_of(2, "é🐍!", 0, 2) == "é"
        assert mod.slice_of(4, "é🐍!", 2, 6) == "🐍"

    def test_append_slice_growing(self):
        src = """
        from strbuilder import StrBuilder

        def slice_of(cap: int, chunk: str, start: int, end: int) -> str:
            sb = StrBuilder(cap)
            sb.append_slice(chunk, start, end)
            return sb.build()
        """
        mod = self.compile(src)
        # test the growing path
        #                       01234567890ABCDEF
        assert mod.slice_of(3, "aaa hello world !", 4, 15) == "hello world"

        # test out-of-bounds
        with pytest.raises(SPyError, match="IndexError"):
            mod.slice_of(10, "abc", 2, 4)
        with pytest.raises(SPyError, match="IndexError"):
            mod.slice_of(10, "abc", -1, 2)
        with pytest.raises(SPyError, match="IndexError"):
            mod.slice_of(10, "abc", 2, 1)

    def test_append_repeat(self, Builder):
        src = f"""
        from strbuilder import {Builder} as SB

        def repeat_of(capacity: int, chunk: str, n: int) -> str:
            sb = SB(capacity)
            sb.append_repeat(chunk, n)
            return sb.build()
        """
        mod = self.compile(src)
        assert mod.repeat_of(6, "ab", 3) == "ababab"
        assert mod.repeat_of(2, "é", 1) == "é"
        assert mod.repeat_of(0, "x", 0) == ""
        assert mod.repeat_of(0, "", 5) == ""

    def test_append_repeat_growing(self):
        src = """
        from strbuilder import StrBuilder

        def repeat_of(capacity: int, chunk: str, n: int) -> str:
            sb = StrBuilder(capacity)
            sb.append_repeat(chunk, n)
            return sb.build()
        """
        mod = self.compile(src)
        assert mod.repeat_of(4, "ab", 3) == "ababab"
        assert mod.repeat_of(5, "ab", 3) == "ababab"
