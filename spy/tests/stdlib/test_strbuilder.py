import pytest

from spy.tests.support import CompilerTest


@pytest.fixture(params=["StrBuilder", "Unsafe"])
def Builder(request):
    if request.param == "StrBuilder":
        return "StrBuilder"
    elif request.param == "Unsafe":
        return "UnsafeFixedStrBuilder"
    else:
        assert False


class TestStrBuilder(CompilerTest):
    def test_simple(self, Builder):
        src = f"""
        from strbuilder import {Builder}

        def concat(cap: int, a: str, b: str, c: str) -> str:
            sb = {Builder}(cap)
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

    def test_unsafe_append_slice(self):
        src = """
        from strbuilder import UnsafeFixedStrBuilder

        def slice_of(capacity: int, chunk: str, start: int, end: int) -> str:
            sb = UnsafeFixedStrBuilder(capacity)
            sb.append_slice(chunk, start, end)
            return sb.build()

        def mix() -> str:
            sb = UnsafeFixedStrBuilder(6)
            sb.append("ab")
            sb.append_slice("xxcdefyy", 2, 6)
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
        assert mod.mix() == "abcdef"

    def test_unsafe_append_repeat(self):
        src = """
        from strbuilder import UnsafeFixedStrBuilder

        def repeat_of(capacity: int, chunk: str, n: int) -> str:
            sb = UnsafeFixedStrBuilder(capacity)
            sb.append_repeat(chunk, n)
            return sb.build()

        def mix() -> str:
            sb = UnsafeFixedStrBuilder(9)
            sb.append_repeat("ab", 3)
            sb.append("x")
            sb.append_repeat("-", 2)
            return sb.build()
        """
        mod = self.compile(src)
        assert mod.repeat_of(6, "ab", 3) == "ababab"
        assert mod.repeat_of(2, "é", 1) == "é"
        assert mod.repeat_of(0, "x", 0) == ""
        assert mod.repeat_of(0, "", 5) == ""
        assert mod.mix() == "abababx--"
