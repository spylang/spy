import pytest
from spy.fqn import FQN
from spy.errors import SPyError
from spy.vm.b import B
from spy.fqn import FQN
from spy.tests.support import (CompilerTest, skip_backends, no_backend,
                               expect_errors, only_interp, no_C)

class TestNumeric(CompilerTest):

    def test_i8_simple(self):
        mod = self.compile(
        """
        def foo(x: i32) -> i8:
            return x

        def bar(x: i8) -> i32:
            return x
        """)
        assert mod.foo(42) == 42
        assert mod.foo(128) == -128
        assert mod.bar(42) == 42
        assert mod.bar(-1) == -1
        assert mod.bar(128) == -128

    @pytest.mark.skip
    def test_i8_ops(self):
        mod = self.compile(
        """
        def add(x: i8, y: i8) -> i8:
            return x + y

        def sub(x: i8, y: i8) -> i8:
            return x - y

        def mul(x: i8, y: i8) -> i8:
            return x * y

        def div(x: i8, y: i8) -> i8:
            return x // y

        def mod(x: i8, y: i8) -> i8:
            return x % y

        def neg(x: i8) -> i8:
            return -x
        """)

        assert mod.add(127, 1) == -128
        assert mod.sub(-128, 1) == 127
        assert mod.mul(4, 8) == 32
        assert mod.mul(64, 4) == 0
        assert mod.div(100, 3) == 33
        assert mod.mod(100, 3) == 1
        assert mod.neg(127) == -127
        assert mod.neg(-128) == -128

    @pytest.mark.skip
    def test_i8_comparisons(self):
        from fixedint import Int8
        mod = self.compile(
        """
        def eq(x: i8, y: i8) -> bool:
            return x == y

        def ne(x: i8, y: i8) -> bool:
            return x != y

        def lt(x: i8, y: i8) -> bool:
            return x < y

        def le(x: i8, y: i8) -> bool:
            return x <= y

        def gt(x: i8, y: i8) -> bool:
            return x > y

        def ge(x: i8, y: i8) -> bool:
            return x >= y
        """)

        assert mod.eq(42, 42)
        assert not mod.eq(42, 43)
        assert mod.ne(42, 43)
        assert not mod.ne(42, 42)
        assert mod.lt(-10, 10)
        assert not mod.lt(10, -10)
        assert mod.le(42, 42)
        assert mod.le(41, 42)
        assert mod.gt(43, 42)
        assert not mod.gt(42, 42)
        assert mod.ge(42, 42)
        assert mod.ge(43, 42)
