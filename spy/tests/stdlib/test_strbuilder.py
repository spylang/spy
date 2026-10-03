from spy.errors import SPyError
from spy.tests.support import CompilerTest


class TestStrBuilder(CompilerTest):
    def test_build(self):
        src = """
        from strbuilder import StrBuilder

        def concatenate(capacity: int, first: str, second: str, third: str) -> str:
            sb = StrBuilder(capacity)
            for chunk in [first, second, third]:
                sb.append(chunk)
            return sb.build()
        """
        mod = self.compile(src)

        assert mod.concatenate(0, "", "", "") == ""
        assert mod.concatenate(5, "", "hello", "") == "hello"
        assert mod.concatenate(7, "abc", "def", "!") == "abcdef!"
        assert mod.concatenate(7, "é", "🐍", "!") == "é🐍!"
        assert mod.concatenate(4, "a\x00", "b", "\x00") == "a\x00b\x00"

    def test_negative_capacity(self):
        src = """
        from strbuilder import StrBuilder

        def negative_capacity() -> None:
            sb = StrBuilder(-1)
        """
        mod = self.compile(src)
        with SPyError.raises("W_ValueError"):
            mod.negative_capacity()

    def test_build_underfilled(self):
        src = """
        from strbuilder import StrBuilder

        def build_underfilled() -> str:
            sb = StrBuilder(6)
            sb.append("hello")
            return sb.build()
        """
        mod = self.compile(src)
        with SPyError.raises(
            "W_ValueError",
            match="StrBuilder is not completely filled",
        ):
            mod.build_underfilled()

    def test_append_over_capacity(self):
        src = """
        from strbuilder import StrBuilder

        def append_over_capacity() -> None:
            sb = StrBuilder(4)
            sb.append("hello")
        """
        mod = self.compile(src)
        with SPyError.raises(
            "W_ValueError",
            match="StrBuilder capacity exceeded",
        ):
            mod.append_over_capacity()

    def test_shared_state(self):
        src = """
        from strbuilder import StrBuilder

        def append_middle(sb: StrBuilder) -> None:
            sb.append("middle")

        def build() -> str:
            sb = StrBuilder(15)
            alias = sb
            sb.append("left")
            append_middle(alias)
            sb.append("right")
            return alias.build()
        """
        mod = self.compile(src)
        assert mod.build() == "leftmiddleright"

    def test_append_after_build(self):
        src = """
        from strbuilder import StrBuilder

        def append_after_build() -> None:
            sb = StrBuilder(5)
            sb.append("hello")
            sb.build()
            sb.append("")
        """
        mod = self.compile(src)
        with SPyError.raises("W_ValueError"):
            mod.append_after_build()

    def test_append_slice(self):
        src = """
        from strbuilder import StrBuilder

        def slice_of(capacity: int, chunk: str, start: int, end: int) -> str:
            sb = StrBuilder(capacity)
            sb.append_slice(chunk, start, end)
            return sb.build()

        def mix() -> str:
            sb = StrBuilder(6)
            sb.append("ab")
            sb.append_slice("xxcdefyy", 2, 6)
            return sb.build()

        def append_slice_over_capacity() -> None:
            sb = StrBuilder(2)
            sb.append_slice("abcdef", 0, 3)
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

        with SPyError.raises(
            "W_ValueError",
            match="StrBuilder capacity exceeded",
        ):
            mod.append_slice_over_capacity()

    def test_build_after_build(self):
        src = """
        from strbuilder import StrBuilder

        def build_after_build() -> str:
            sb = StrBuilder(5)
            sb.append("hello")
            sb.build()
            return sb.build()
        """
        mod = self.compile(src)
        with SPyError.raises("W_ValueError"):
            mod.build_after_build()
