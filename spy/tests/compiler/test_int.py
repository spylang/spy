import pytest
from spy.fqn import FQN
from spy.errors import SPyError
from spy.vm.b import B
from spy.fqn import FQN
from spy.tests.support import (CompilerTest, skip_backends, no_backend,
                               expect_errors, only_interp, no_C)

class TestInt(CompilerTest):

    def test_i32_ops(self):
        mod = self.compile("""
        def add(x: i32, y: i32) -> i32:      return x + y
        def sub(x: i32, y: i32) -> i32:      return x - y
        def mul(x: i32, y: i32) -> i32:      return x * y
        def mod(x: i32, y: i32) -> i32:      return x % y
        def div(x: i32, y: i32) -> f64:      return x / y
        def floordiv(x: i32, y: i32) -> i32: return x // y
        def neg(x: i32) -> i32: return -x
        """)
        assert mod.add(1, 2) == 3
        assert mod.sub(3, 4) == -1
        assert mod.mul(5, 6) == 30
        assert mod.mod(10, 3) == 1
        assert mod.div(11, 2) == 5.5
        assert mod.floordiv(11, 2) == 5
        assert mod.neg(-5) == 5

    def test_i32_bitwise(self):
        mod = self.compile("""
        def shl(x: i32, y: i32) -> i32: return x << y
        def shr(x: i32, y: i32) -> i32: return x >> y
        def b_and(x: i32, y: i32) -> i32: return x & y
        def b_or(x: i32, y: i32) -> i32: return x | y
        def b_xor(x: i32, y: i32) -> i32: return x ^ y
        """)
        assert mod.shl(128, 4) == 128 << 4
        assert mod.shr(128, 4) == 128 >> 4
        assert mod.b_and(7, 3) == 7 & 3
        assert mod.b_and(127, 7) == 127 & 7
        assert mod.b_or(127, 123) == 127 | 123
        assert mod.b_or(127, 0) == 127 | 0
        assert mod.b_xor(16, 15) == 16 ^ 15
        assert mod.b_xor(16, 0) == 16 ^ 0

    def test_i32_cmp(self):
        mod = self.compile("""
        def cmp_eq (x: i32, y: i32) -> bool: return x == y
        def cmp_neq(x: i32, y: i32) -> bool: return x != y
        def cmp_lt (x: i32, y: i32) -> bool: return x  < y
        def cmp_lte(x: i32, y: i32) -> bool: return x <= y
        def cmp_gt (x: i32, y: i32) -> bool: return x  > y
        def cmp_gte(x: i32, y: i32) -> bool: return x >= y
        """)
        assert mod.cmp_eq(5, 5) is True
        assert mod.cmp_eq(5, 6) is False
        #
        assert mod.cmp_neq(5, 5) is False
        assert mod.cmp_neq(5, 6) is True
        #
        assert mod.cmp_lt(5, 6) is True
        assert mod.cmp_lt(5, 5) is False
        assert mod.cmp_lt(6, 5) is False
        #
        assert mod.cmp_lte(5, 6) is True
        assert mod.cmp_lte(5, 5) is True
        assert mod.cmp_lte(6, 5) is False
        #
        assert mod.cmp_gt(5, 6) is False
        assert mod.cmp_gt(5, 5) is False
        assert mod.cmp_gt(6, 5) is True
        #
        assert mod.cmp_gte(5, 6) is False
        assert mod.cmp_gte(5, 5) is True
        assert mod.cmp_gte(6, 5) is True


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
