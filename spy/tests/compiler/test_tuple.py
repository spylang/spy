import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors


class TestTuple(CompilerTest):
    """
    These are only few of the tests about tuples, mostly to check that:

      1. tuple[T1, T2, ...] does the right thing

      2. the tuple literal syntax "(a, b, c)" works

    The actual behavior of tuple objects is tested by stdlib/test__tuple.py and
    test_interp_tuple.py
    """

    def test_literal(self):
        mod = self.compile("""
        def foo() -> tuple[i32, i32]:
            return 1, 2
        """)
        tup = mod.foo()
        assert tup == (1, 2)

    def test_unpacking_blue(self):
        mod = self.compile("""
        @blue
        def make_tuple():
            return 1, 2, 'hello'

        def foo() -> i32:
            a, b, c = make_tuple()
            return a + b
        """)
        x = mod.foo()
        assert x == 3

    def test_unpacking_red(self):
        mod = self.compile("""
        def make_tuple() -> tuple[i32, i32, str]:
            return 1, 2, 'hello'

        def foo() -> i32:
            a, b, c = make_tuple()
            return a + b
        """)
        x = mod.foo()
        assert x == 3
