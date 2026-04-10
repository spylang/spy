"""
Tests for the @force_inline decorator.
"""

import textwrap

import pytest

from spy.backend.spy import SPyBackend
from spy.errors import SPyError
from spy.tests.support import CompilerTest, only_doppler
from spy.util import print_diff


@only_doppler
class TestForceInline(CompilerTest):
    def assert_dump(self, expected: str, *, modname: str = "test") -> None:
        b = SPyBackend(self.vm)
        got = b.dump_mod(modname).strip()
        expected = textwrap.dedent(expected).strip()
        if got != expected:
            print_diff(expected, got, "expected", "got")
            pytest.fail("assert_dump failed")

    # ------------------------------------------------------------------ #
    # Basic correctness: inlined functions still produce the right value #
    # ------------------------------------------------------------------ #

    def test_basic_inline_correctness(self):
        mod = self.compile("""
        @force_inline
        def double(x: i32) -> i32:
            return x * 2

        def foo(a: i32) -> i32:
            return double(a)
        """)
        assert mod.foo(3) == 6
        assert mod.foo(0) == 0
        assert mod.foo(-5) == -10

    def test_inline_two_args(self):
        mod = self.compile("""
        @force_inline
        def add(x: i32, y: i32) -> i32:
            return x + y

        def foo(a: i32, b: i32) -> i32:
            return add(a, b)
        """)
        assert mod.foo(3, 4) == 7

    def test_inline_called_multiple_times(self):
        mod = self.compile("""
        @force_inline
        def square(x: i32) -> i32:
            return x * x

        def foo(a: i32) -> i32:
            return square(a) + square(a + 1)
        """)
        assert mod.foo(3) == 9 + 16
        assert mod.foo(0) == 0 + 1

    def test_inline_with_expr_arg(self):
        mod = self.compile("""
        @force_inline
        def double(x: i32) -> i32:
            return x * 2

        def foo(a: i32, b: i32) -> i32:
            return double(a + b)
        """)
        assert mod.foo(2, 3) == 10

    # ------------------------------------------------------------------ #
    # Dump tests: verify the redshifted source looks correctly inlined   #
    # ------------------------------------------------------------------ #

    def test_dump_simple_inline(self):
        self.compile("""
        @force_inline
        def double(x: i32) -> i32:
            return x * 2

        def foo(a: i32) -> i32:
            return double(a)
        """)
        # The inlined call `double(a)` becomes `a * 2`.
        # @force_inline functions themselves are still present in the dump
        # (they remain valid W_ASTFuncs), but callers no longer call them.
        self.assert_dump("""
        @force_inline
        def double(x: i32) -> i32:
            return x * 2

        def foo(a: i32) -> i32:
            return a * 2
        """)

    def test_dump_inline_two_args(self):
        self.compile("""
        @force_inline
        def add(x: i32, y: i32) -> i32:
            return x + y

        def foo(a: i32, b: i32) -> i32:
            return add(a, b)
        """)
        self.assert_dump("""
        @force_inline
        def add(x: i32, y: i32) -> i32:
            return x + y

        def foo(a: i32, b: i32) -> i32:
            return a + b
        """)

    def test_dump_inline_multiple_callsites(self):
        self.compile("""
        @force_inline
        def square(x: i32) -> i32:
            return x * x

        def foo(a: i32) -> i32:
            return square(a) + square(a + 1)
        """)
        self.assert_dump("""
        @force_inline
        def square(x: i32) -> i32:
            return x * x

        def foo(a: i32) -> i32:
            return a * a + (a + 1) * (a + 1)
        """)

    # ------------------------------------------------------------------ #
    # --no-inline: the flag must suppress inlining                       #
    # ------------------------------------------------------------------ #

    def test_no_inline_flag_suppresses_inlining(self):
        self.compile(
            """
        @force_inline
        def double(x: i32) -> i32:
            return x * 2

        def foo(a: i32) -> i32:
            return double(a)
        """,
            no_inline=True,
        )
        # With no_inline, the call is NOT replaced
        self.assert_dump("""
        @force_inline
        def double(x: i32) -> i32:
            return x * 2

        def foo(a: i32) -> i32:
            return `test::double`(a)
        """)

    def test_no_inline_still_executes_correctly(self):
        mod = self.compile(
            """
        @force_inline
        def double(x: i32) -> i32:
            return x * 2

        def foo(a: i32) -> i32:
            return double(a)
        """,
            no_inline=True,
        )
        assert mod.foo(5) == 10

    # ------------------------------------------------------------------ #
    # Error cases                                                          #
    # ------------------------------------------------------------------ #

    def test_error_multi_statement_body(self):
        src = """
        @force_inline
        def bad(x: i32) -> i32:
            y: i32 = x + 1
            return y

        def foo(a: i32) -> i32:
            return bad(a)
        """
        with pytest.raises(SPyError, match="@force_inline"):
            self.compile(src)

    def test_error_multiple_returns(self):
        src = """
        @force_inline
        def bad(x: i32) -> i32:
            return x
            return x + 1

        def foo(a: i32) -> i32:
            return bad(a)
        """
        with pytest.raises(SPyError, match="@force_inline"):
            self.compile(src)

    # ------------------------------------------------------------------ #
    # Edge cases                                                         #
    # ------------------------------------------------------------------ #

    def test_inline_constant_body(self):
        mod = self.compile("""
        @force_inline
        def forty_two() -> i32:
            return 42

        def foo() -> i32:
            return forty_two()
        """)
        assert mod.foo() == 42

    def test_inline_inside_nested_expr(self):
        mod = self.compile("""
        @force_inline
        def inc(x: i32) -> i32:
            return x + 1

        def foo(a: i32) -> i32:
            return inc(inc(a))
        """)
        assert mod.foo(3) == 5

    def test_force_inline_does_not_affect_blue(self):
        mod = self.compile("""
        @blue
        def SCALE():
            return 3

        @force_inline
        def triple(x: i32) -> i32:
            return x * SCALE()

        def foo(a: i32) -> i32:
            return triple(a)
        """)
        assert mod.foo(4) == 12
