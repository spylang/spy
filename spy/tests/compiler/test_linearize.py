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

    def test_call_order(self, capfd):
        # see also the related TestNative.test_call_order.
        #
        # In C, call order is not specified. This test happened to pass "by chance" when
        # compiled to WASM (the default for the C backend), but to fail when compiled to
        # x86_64, which is what we test in TestNative.
        src = """
        def f1() -> i32:
            print('f1')
            return 10

        def f2() -> i32:
            print('f2')
            return 3

        def sub(a: i32, b: i32) -> i32:
            return a - b

        def foo() -> i32:
            return sub(f1(), f2())
        """
        mod = self.compile(src)
        assert mod.foo() == 7
        if self.backend == "C":
            mod.ll.call("spy_flush")
        out, err = capfd.readouterr()
        assert out.splitlines() == ["f1", "f2"]
        #
        if self.backend == "linearize":
            expected = """
            def foo() -> i32:
                $v0: i32 = `test::f1`()
                $v1: i32 = `test::f2`()
                return `test::sub`($v0, $v1)
            """
            self.assert_linearize("foo", expected)

    def test_no_spill_for_pure_exprs(self):
        src = """
        def add(x: i32, y: i32) -> i32:
            return x + y

        def foo(x: i32) -> i32:
            return add(x + 1, x + 2)
        """
        mod = self.compile(src)
        assert mod.foo(10) == 23
        #
        if self.backend == "linearize":
            expected = """
            def foo(x: i32) -> i32:
                return `test::add`(x + 1, x + 2)
            """
            self.assert_linearize("foo", expected)

    def test_no_spill_for_pure_with_impure_args(self):
        src = """
        def f1() -> i32:
            return 1

        def f2() -> i32:
            return 2

        def foo() -> i32:
            return f1() + f2()
        """
        mod = self.compile(src)
        assert mod.foo() == 3
        #
        if self.backend == "linearize":
            expected = """
            def foo() -> i32:
                $v0: i32 = `test::f1`()
                $v1: i32 = `test::f2`()
                return $v0 + $v1
            """
            self.assert_linearize("foo", expected)

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
