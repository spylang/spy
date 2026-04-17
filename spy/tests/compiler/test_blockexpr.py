import pytest

from spy.tests.support import CompilerTest, expect_errors


class TestBlockExpr(CompilerTest):
    def test_simple(self):
        mod = self.compile("""
        def foo() -> i32:
            return __block__('''
                x: i32 = 1
                x
            ''')
        """)
        assert mod.foo() == 1

    def test_value_only(self):
        mod = self.compile("""
        def foo() -> i32:
            return __block__('''
                42
            ''')
        """)
        assert mod.foo() == 42

    def test_multiple_stmts(self):
        mod = self.compile("""
        def foo() -> i32:
            return __block__('''
                x: i32 = 1
                y: i32 = 2
                x + y
            ''')
        """)
        assert mod.foo() == 3

    def test_in_call_args(self):
        mod = self.compile("""
        def add(a: i32, b: i32) -> i32:
            return a + b

        def f() -> i32:
            return 10

        def g() -> i32:
            return 20

        def foo() -> i32:
            return add(
                __block__('''
                    a: i32 = f()
                    a
                '''),
                __block__('''
                    b: i32 = g()
                    b
                '''),
            )
        """)
        assert mod.foo() == 30

    def test_in_binop(self):
        mod = self.compile("""
        def foo() -> i32:
            return 1 + __block__('''
                x: i32 = 2
                x + 3
            ''')
        """)
        assert mod.foo() == 6
