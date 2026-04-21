import textwrap

import pytest

from spy.backend.spy import FQN_FORMAT, SPyBackend
from spy.fqn import FQN
from spy.tests.support import CompilerTest, with_additional_backends
from spy.util import print_diff
from spy.vm.function import W_ASTFunc


@with_additional_backends(["linearize"])
class TestLinearize(CompilerTest):
    def assert_linearize(
        self, funcname: str, expected: str, *, fqn_format: FQN_FORMAT = "short"
    ) -> None:
        assert self.backend == "linearize"
        fqn = FQN(f"test::{funcname}")
        w_func = self.vm.lookup_global(fqn)
        b = SPyBackend(self.vm, fqn_format=fqn_format)
        b.modname = "test"
        b.dump_w_func(fqn, w_func)
        got = b.out.build().strip()
        expected = textwrap.dedent(expected).strip()
        if got != expected:
            print_diff(expected, got, "expected", "got")
            pytest.fail("assert_linearize failed")

    def test_simple(self):
        src = """
        def foo(x: i32) -> i32:
            return x
        """
        mod = self.compile(src)
        assert mod.foo(42) == 42
        #
        if self.backend == "linearize":
            expected = """
            def foo(x: i32) -> i32:
                return x
            """
            self.assert_linearize("foo", expected)

    @pytest.mark.skip("FIXME")
    def test_call_order(self):
        src = """
        def foo() -> i32:
            return 1

        def bar() -> i32:
            return 2

        def add(a: i32, b: i32) -> i32:
            return a + b

        def main() -> i32:
            return add(foo(), bar())
        """
        mod = self.compile(src)
        assert mod.main() == 3
        #
        if self.backend == "linearize":
            expected = """
            def main() -> i32:
                $v0: i32 = foo()
                $v1: i32 = bar()
                return add($v0, $v1)
            """
            self.assert_linearize("main", expected)

    def test_blockexpr_simple(self):
        src = """
        def foo(a: i32) -> i32:
            return __block__('''
                x: i32 = a
                x
            ''')
        """
        mod = self.compile(src)
        assert mod.foo(7) == 7
        #
        if self.backend == "linearize":
            expected = """
            def foo(a: i32) -> i32:
                x: i32 = a
                return x
            """
            self.assert_linearize("foo", expected)
