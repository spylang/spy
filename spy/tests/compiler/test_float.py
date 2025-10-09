# -*- encoding: utf-8 -*-

from spy.errors import SPyError
from spy.tests.support import CompilerTest


class TestFloat(CompilerTest):
    def test_literal(self):
        mod = self.compile("""
        def foo() -> f64:
            return 12.3
        """)
        assert mod.foo() == 12.3

    def test_BinOp(self):
        mod = self.compile("""
        def add(x: f64, y: f64) -> f64:      return x + y
        def sub(x: f64, y: f64) -> f64:      return x - y
        def mul(x: f64, y: f64) -> f64:      return x * y
        def div(x: f64, y: f64) -> f64:      return x / y
        def floordiv(x: f64, y: f64) -> f64: return x // y
        def mod(x: f64, y: f64) -> f64:      return x % y
        def neg(x: f64) -> f64:              return -x
        """)
        assert mod.add(1.5, 2.6) == 4.1
        assert mod.sub(1.5, 0.2) == 1.3
        assert mod.mul(1.5, 0.5) == 0.75
        assert mod.div(1.5, 2.0) == 0.75
        assert mod.floordiv(10.0, 3.0) == 3.0
        assert mod.mod(10.5, 2.5) == 0.5
        assert mod.neg(-2.5) == 2.5

    def test_zero_division_error(self):
        mod = self.compile("""
        def div(x: f64, y: f64) -> f64:      return x / y
        def floordiv(x: f64, y: f64) -> f64: return x // y
        def mod(x: f64, y: f64) -> f64:      return x % y
        """)
        with SPyError.raises("W_ZeroDivisionError", match="float division by zero"):
            mod.div(1.5, 0.0)
        with SPyError.raises(
            "W_ZeroDivisionError", match="float floor division by zero"
        ):
            mod.floordiv(10.0, 0.0)
        with SPyError.raises("W_ZeroDivisionError", match="float modulo by zero"):
            mod.mod(10.5, 0.0)

    def test_division_mixed_signs(self):
        mod = self.compile("""
        def floordiv(x: f64, y: f64) -> f64: return x // y
        def mod(x: f64, y: f64) -> f64: return x % y
        """)
        assert mod.floordiv(3.5, 1.5) == 2.0
        assert mod.floordiv(3.5, -1.5) == -3.0
        assert mod.floordiv(-3.5, 1.5) == -3.0
        assert mod.floordiv(-3.5, -1.5) == 2.0
        assert mod.mod(3.5, 1.5) == 0.5
        assert mod.mod(3.5, -1.5) == -1.0
        assert mod.mod(-3.5, 1.5) == 1.0
        assert mod.mod(-3.5, -1.5) == -0.5
        assert mod.mod(5.0, float("inf")) == 5.0
        assert mod.mod(-5.0, float("inf")) == float("inf")
        assert mod.mod(5.0, float("-inf")) == float("-inf")
        assert mod.mod(-5.0, float("-inf")) == -5.0

    def test_CompareOp(self):
        mod = self.compile("""
        def cmp_eq (x: f64, y: f64) -> bool: return x == y
        def cmp_neq(x: f64, y: f64) -> bool: return x != y
        def cmp_lt (x: f64, y: f64) -> bool: return x  < y
        def cmp_lte(x: f64, y: f64) -> bool: return x <= y
        def cmp_gt (x: f64, y: f64) -> bool: return x  > y
        def cmp_gte(x: f64, y: f64) -> bool: return x >= y
        """)
        assert mod.cmp_eq(5.1, 5.1) is True
        assert mod.cmp_eq(5.1, 6.2) is False

        assert mod.cmp_neq(5.1, 5.1) is False
        assert mod.cmp_neq(5.1, 6.2) is True

        assert mod.cmp_lt(5.1, 6.2) is True
        assert mod.cmp_lt(5.1, 5.1) is False
        assert mod.cmp_lt(6.2, 5.1) is False

        assert mod.cmp_lte(5.1, 6.2) is True
        assert mod.cmp_lte(5.1, 5.1) is True
        assert mod.cmp_lte(6.2, 5.1) is False

        assert mod.cmp_gt(5.1, 6.2) is False
        assert mod.cmp_gt(5.1, 5.1) is False
        assert mod.cmp_gt(6.2, 5.1) is True

        assert mod.cmp_gte(5.1, 6.2) is False
        assert mod.cmp_gte(5.1, 5.1) is True
        assert mod.cmp_gte(6.2, 5.1) is True

    def test_implicit_conversion(self):
        mod = self.compile("""
        def add(x: f64, y: i32) -> f64: return x + y
        def sub(x: i32, y: f64) -> f64: return x - y
        def div(x: f64, y: i32) -> f64: return x / y

        def add_i8(x: f64, y: i8) -> f64: return x + y
        def add_u8(x: f64, y: u8) -> f64: return x + y
        """)
        assert mod.add(1.5, 2) == 3.5
        assert mod.sub(10, 0.5) == 9.5
        assert mod.div(1.5, 2) == 0.75
        assert mod.add_i8(1.5, 2) == 3.5
        assert mod.add_u8(1.5, 2) == 3.5

    def test_int_to_float(self):
        mod = self.compile("""
        def to_f64(x: i32) -> f64:
            res = f64(x)
            return res
        """)
        assert mod.to_f64(42) == 42.0
