import pytest

from spy.tests.support import (
    CompilerTest,
    expect_errors,
    only_interp,
    skip_backends,
)


class TestForceInline(CompilerTest):
    @only_interp
    def test_decorator(self):
        mod = self.compile("""
        from __spy__ import force_inline

        @force_inline
        def inc(x: i32) -> i32:
            return x + 1

        """)
        assert mod.inc.w_func.is_force_inline

    def test_error_applied_to_blue_function(self):
        src = """
        from __spy__ import force_inline

        @force_inline
        @blue
        def inc(x: i32) -> i32:
            return x + 1

        def foo(x: i32) -> i32:
            return inc(x)
        """
        errors = expect_errors(
            "@force_inline cannot be applied to @blue functions",
        )
        self.compile_raises(src, "foo", errors, error_reporting="eager")

    def test_none_return_type(self):
        mod = self.compile("""
        from __spy__ import force_inline

        @force_inline
        def greet(x: i32) -> None:
            print(x)

        def foo() -> None:
            greet(42)
        """)
        mod.foo()

    def test_error_missing_return(self):
        src = """
        from __spy__ import force_inline

        @force_inline
        def inc(x: i32) -> i32:
            var y = x + 1

        def foo() -> i32:
            return inc(3)
        """
        errors = expect_errors(
            "@force_inline requires a single tail return",
        )
        self.compile_raises(src, "foo", errors, error_reporting="eager")

    def test_error_multiple_returns(self):
        src = """
        from __spy__ import force_inline

        @force_inline
        def clamp(x: i32, lo: i32) -> i32:
            if x < lo:
                return lo
            return x

        def foo() -> i32:
            return clamp(3, 0)
        """
        errors = expect_errors(
            "@force_inline requires a single tail return",
            ("`return` must be the last statement of the body", "return lo"),
        )
        self.compile_raises(src, "foo", errors, error_reporting="eager")
