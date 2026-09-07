from spy.errors import SPyError
from spy.tests.support import (
    CompilerTest,
    expect_errors,
)


class TestStrictScoping(CompilerTest):
    """
    These tests are loosely based on the snippets in docs/src/reference/scoping.md
    """

    def test_decl_forms(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> i32:
            var x: i32 = 42
            return x
        """
        mod = self.compile(src)
        assert mod.foo() == 42

    def test_decl_initializer(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> i32:
            var x: i32
            x = 42
            return x
        """
        mod = self.compile(src)
        assert mod.foo() == 42
