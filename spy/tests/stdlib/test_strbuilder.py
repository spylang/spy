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
