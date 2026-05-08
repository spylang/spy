import pytest

from spy.tests.support import CompilerTest


class TestMisc(CompilerTest):
    def test_COLOR(self):
        mod = self.compile("""
        from __spy__ import COLOR

        def foo() -> str:
            x = 42
            return COLOR(x)

        def bar() -> str:
            x = 42
            x = 43
            return COLOR(x)
        """)
        assert mod.foo() == "blue"
        assert mod.bar() == "red"

    def test_is_compiled(self):
        mod = self.compile("""
        from __spy__ import is_compiled

        def foo() -> bool:
            return is_compiled()
        """)
        if self.backend in ("interp", "doppler"):
            assert mod.foo() == False
        else:
            assert mod.foo() == True
