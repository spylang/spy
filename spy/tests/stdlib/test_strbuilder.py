import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest


@pytest.mark.xfail(strict=True, reason="StrBuilder is not implemented yet")
class TestStrBuilder(CompilerTest):
    def test_build(self):
        src = """
        from strbuilder import StrBuilder

        def concatenate(capacity: int, chunks: list[str]) -> str:
            sb = StrBuilder(capacity)
            for chunk in chunks:
                sb.append(chunk)
            return sb.build()
        """
        mod = self.compile(src)

        for capacity in (0, 1, 5, 6, 7, 32):
            for chunks in (
                [],
                [""],
                ["hello"],
                ["abc", "def", "!"],
                ["", "abc", "", "def", "!", ""],
                ["a", "much longer chunk", "b", "c"],
                ["é", "🐍", "!"],
                ["a\x00", "b", "\x00"],
            ):
                assert mod.concatenate(capacity, chunks) == "".join(chunks)

    def test_shared_state(self):
        src = """
        from strbuilder import StrBuilder

        def append_middle(sb: StrBuilder) -> None:
            sb.append("middle")

        def build(capacity: int) -> str:
            sb = StrBuilder(capacity)
            alias = sb
            sb.append("left")
            append_middle(alias)
            sb.append("right")
            return alias.build()
        """
        mod = self.compile(src)
        for capacity in (0, 5, 15, 32):
            assert mod.build(capacity) == "leftmiddleright"

    def test_append_after_build(self):
        src = """
        from strbuilder import StrBuilder

        def append_after_build(capacity: int, chunk: str) -> None:
            sb = StrBuilder(capacity)
            alias = sb
            sb.append("hello")
            result = sb.build()
            alias.append(chunk)
        """
        mod = self.compile(src)
        for capacity in (0, 3, 5, 32):
            for chunk in ("!", ""):
                with SPyError.raises("W_ValueError"):
                    mod.append_after_build(capacity, chunk)

    def test_build_after_build(self):
        src = """
        from strbuilder import StrBuilder

        def build_after_build(capacity: int, chunk: str) -> str:
            sb = StrBuilder(capacity)
            alias = sb
            sb.append(chunk)
            result = sb.build()
            return alias.build()
        """
        mod = self.compile(src)
        for capacity in (0, 3, 5, 32):
            for chunk in ("hello", ""):
                with SPyError.raises("W_ValueError"):
                    mod.build_after_build(capacity, chunk)
