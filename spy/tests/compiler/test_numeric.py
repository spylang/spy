import pytest
from spy.fqn import FQN
from spy.errors import SPyError
from spy.vm.b import B
from spy.fqn import FQN
from spy.tests.support import (CompilerTest, skip_backends, no_backend,
                               expect_errors, only_interp, no_C)

class TestNumeric(CompilerTest):

    def test_i8_simple(self):
        from fixedint import Int8
        mod = self.compile(
        """
        def foo(x: i32) -> i8:
            return x

        def bar(x: i8) -> i32:
            return x
        """)
        assert mod.foo(42) == 42
        assert mod.foo(128) == -128
        assert mod.bar(Int8(42)) == 42
        assert mod.bar(Int8(-1)) == -1
        assert mod.bar(Int8(128)) == -128

    def test_i8_ops(self):
        from fixedint import Int8
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

        assert mod.add(Int8(127), Int8(1)) == Int8(-128)
        assert mod.sub(Int8(-128), Int8(1)) == Int8(127)
        assert mod.mul(Int8(4), Int8(8)) == Int8(32)
        assert mod.mul(Int8(64), Int8(4)) == Int8(0)
        assert mod.div(Int8(100), Int8(3)) == Int8(33)
        assert mod.mod(Int8(100), Int8(3)) == Int8(1)
        assert mod.neg(Int8(127)) == Int8(-127)
        assert mod.neg(Int8(-128)) == Int8(-128)

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

        assert mod.eq(Int8(42), Int8(42))
        assert not mod.eq(Int8(42), Int8(43))
        assert mod.ne(Int8(42), Int8(43))
        assert not mod.ne(Int8(42), Int8(42))
        assert mod.lt(Int8(-10), Int8(10))
        assert not mod.lt(Int8(10), Int8(-10))
        assert mod.le(Int8(42), Int8(42))
        assert mod.le(Int8(41), Int8(42))
        assert mod.gt(Int8(43), Int8(42))
        assert not mod.gt(Int8(42), Int8(42))
        assert mod.ge(Int8(42), Int8(42))
        assert mod.ge(Int8(43), Int8(42))
