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

    def test_decl_use_before_ok_across_functions(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> i32:
            return x

        const x: i32 = 42
        """
        mod = self.compile(src)
        assert mod.foo() == 42

    def test_decl_use_before(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> None:
            x
            var x: i32 = 1
        """
        errors = expect_errors(
            "name `x` is not defined",
            ("used before its declaration", "x"),
            ("declared later here", "var x: i32 = 1"),
        )
        self.compile_raises(src, "foo", errors)

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

    def test_decl_auto(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> i32:
            const x: auto = 42
            return x

        def bar() -> str:
            const y = "hello"
            return y
        """
        mod = self.compile(src)
        assert mod.foo() == 42
        assert mod.bar() == "hello"

    def test_decl_auto_no_initializer(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> i32:
            var x: auto
            x = 42
            return x
        """
        mod = self.compile(src)
        assert mod.foo() == 42

    def test_NameError(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> None:
            nope
        """
        errors = expect_errors(
            "name `nope` is not defined",
            ("not found in this scope", "nope"),
        )
        self.compile_raises(src, "foo", errors)

    def test_scope_block_if(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> None:
            if True:
                const x: i32 = 1
            x
        """
        errors = expect_errors(
            "name `x` is not defined",
            ("not found in this scope", "x"),
        )
        self.compile_raises(src, "foo", errors)

    def test_scope_shadow(self):
        src = """
        from __spy__ import strict_scoping

        def foo(cond: bool) -> str:
            const x: str = "outer"
            if cond:
                const x: str = "inner"
                return x
            return x
        """
        mod = self.compile(src)
        assert mod.foo(True) == "inner"
        assert mod.foo(False) == "outer"

    def test_scope_branch_local(self):
        src = """
        from __spy__ import strict_scoping

        def foo() -> None:
            if True:
                var x: i32 = 1
            else:
                var x: i32 = 2
            x
        """
        errors = expect_errors(
            "name `x` is not defined",
            ("not found in this scope", "x"),
        )
        self.compile_raises(src, "foo", errors)

    def test_scope_branch_local_shared(self):
        src = """
        from __spy__ import strict_scoping

        def foo(cond: bool) -> i32:
            var x: i32
            if cond:
                x = 1
            else:
                x = 2
            return x
        """
        mod = self.compile(src)
        assert mod.foo(True) == 1
        assert mod.foo(False) == 2
