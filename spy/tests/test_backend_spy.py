import pytest
import textwrap
from spy.vm.vm import SPyVM
from spy.vm.function import W_ASTFunc
from spy.backend.spy import SPyBackend
from spy.util import print_diff
from spy.tests.support import CompilerTest, only_interp

@only_interp
class TestSPyBackend(CompilerTest):

    def assert_dump(self, w_func: W_ASTFunc, expected: str) -> None:
        b = SPyBackend(self.vm)
        got = b.dump_w_func(w_func).strip()
        expected = textwrap.dedent(expected).strip()
        if got != expected:
            print_diff(expected, got, 'expected', 'got')
            pytest.fail('assert_dump failed')

    def test_simple(self):
        mod = self.compile("""
        def foo() -> i32:
            pass
        """)
        self.assert_dump(mod.foo.w_func, """
        def foo() -> i32:
            pass
        """)

    def test_args_and_return(self):
        mod = self.compile("""
        def foo(x: i32, y: i32) -> i32:
            return 42
        """)
        self.assert_dump(mod.foo.w_func, """
        def foo(x: i32, y: i32) -> i32:
            return 42
        """)

    def test_expr_precedence(self):
        mod = self.compile("""
        def foo() -> void:
            a = 1 + 2 * 3
            b = 1 + (2 * 3)
            c = (1 + 2) * 3
        """)
        self.assert_dump(mod.foo.w_func, """
        def foo() -> void:
            a = 1 + 2 * 3
            b = 1 + 2 * 3
            c = (1 + 2) * 3
        """)

    def test_vardef(self):
        mod = self.compile("""
        def foo() -> void:
            x: i32 = 1
        """)
        self.assert_dump(mod.foo.w_func, """
        def foo() -> void:
            x: i32
            x = 1
        """)
