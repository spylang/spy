import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, only_interp


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

    def test_as_red(self):
        src = """
        from __spy__ import COLOR, as_red

        def foo() -> str:
            return COLOR(as_red(42))
        """
        mod = self.compile(src)
        assert mod.foo() == "red"

    @only_interp
    def test_lookup_fqn(self):
        src = """
        from __spy__ import lookup_fqn

        def foo() -> str:
            bar = lookup_fqn('test::bar')
            return bar() + '-foo'
        """
        self.write_file("y.spy", src)
        #
        mod = self.compile("""
        from y import foo

        def bar() -> str:
            return 'bar'

        def main() -> str:
            return foo() + '-main'
        """)
        assert mod.main() == "bar-foo-main"

    @only_interp
    def test_lookup_fqn_not_found(self):
        src = """
        from __spy__ import lookup_fqn

        w_x = lookup_fqn("test::does_not_exist")
        """
        with SPyError.raises("W_ValueError", match="FQN not found"):
            self.compile(src)
