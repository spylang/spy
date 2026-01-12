import math

import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest


@pytest.fixture(params=["f64", "f32"])
def float_type(request):
    return request.param


class TestFloat(CompilerTest):
    def test_literal(self):
        mod = self.compile("""
        def foo() -> f64:
            return 12.3
        """)
        assert mod.foo() == 12.3

    def test_BinOp(self, float_type):
        mod = self.compile(f"""
        T = {float_type}
        def add(x: T, y: T) -> T:      return x + y
        def sub(x: T, y: T) -> T:      return x - y
        def mul(x: T, y: T) -> T:      return x * y
        def div(x: T, y: T) -> T:      return x / y
        def floordiv(x: T, y: T) -> T: return x // y
        def mod(x: T, y: T) -> T:      return x % y
        def neg(x: T) -> T:              return -x
        """)
        assert math.isclose(mod.add(1.5, 2.6), 4.1, rel_tol=1e-6)
        assert math.isclose(mod.sub(1.5, 0.2), 1.3, rel_tol=1e-6)
        assert mod.mul(1.5, 0.5) == 0.75
        assert mod.div(1.5, 2.0) == 0.75
        assert mod.floordiv(10.0, 3.0) == 3.0
        assert mod.mod(10.5, 2.5) == 0.5
        assert mod.neg(-2.5) == 2.5

    def test_zero_division_error(self, float_type):
        mod = self.compile(f"""
        T = {float_type}
        def div(x: T, y: T) -> T:      return x / y
        def floordiv(x: T, y: T) -> T: return x // y
        def mod(x: T, y: T) -> T:      return x % y
        """)
        with SPyError.raises("W_ZeroDivisionError", match="float division by zero"):
            mod.div(1.5, 0.0)
        with SPyError.raises(
            "W_ZeroDivisionError", match="float floor division by zero"
        ):
            mod.floordiv(10.0, 0.0)
        with SPyError.raises("W_ZeroDivisionError", match="float modulo by zero"):
            mod.mod(10.5, 0.0)

    def test_division_mixed_signs(self, float_type):
        mod = self.compile(f"""
        T = {float_type}
        def floordiv(x: T, y: T) -> T: return x // y
        def mod(x: T, y: T) -> T: return x % y
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

    def test_CompareOp(self, float_type):
        mod = self.compile(f"""
        T = {float_type}
        def cmp_eq (x: T, y: T) -> bool: return x == y
        def cmp_neq(x: T, y: T) -> bool: return x != y
        def cmp_lt (x: T, y: T) -> bool: return x  < y
        def cmp_lte(x: T, y: T) -> bool: return x <= y
        def cmp_gt (x: T, y: T) -> bool: return x  > y
        def cmp_gte(x: T, y: T) -> bool: return x >= y
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
        def add_u32(x: f64, y: u32) -> f64: return x + y
        def add_f32(x: f64, y:f32) -> f64: return x + y
        """)
        assert mod.add(1.5, 2) == 3.5
        assert mod.sub(10, 0.5) == 9.5
        assert mod.div(1.5, 2) == 0.75
        assert mod.add_i8(1.5, 2) == 3.5
        assert mod.add_u8(1.5, 2) == 3.5
        assert mod.add_u32(1.5, 2) == 3.5
        assert mod.add_f32(1.5, 2.0) == 3.5

    def test_explicit_conversion(self):
        mod = self.compile("""
        def i32_to_f64(x: i32) -> f64: return f64(x)
        def f32_to_f64(x: f32) -> f64: return f64(x)
        def f64_to_i32(x: f64) -> i32: return i32(x)
        def f32_to_i32(x: f32) -> i32: return i32(x)
        """)
        assert mod.i32_to_f64(42) == 42.0
        assert mod.f32_to_f64(42.0) == 42.0
        assert mod.f64_to_i32(42.0) == 42
        assert mod.f32_to_i32(42.0) == 42
