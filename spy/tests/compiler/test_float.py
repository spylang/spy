import math

import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest


@pytest.fixture(params=["f64", "f32"])
def float_type(request):
    return request.param


class TestFloat(CompilerTest):
    def test_literal(self):
        src = """
        def a() -> f64:
            return 1.5  # implicitly f64

        def b() -> f64:
            return f64(2.5)

        def c() -> f32:
            return f32(3.5)
        """
        mod = self.compile(src)
        assert mod.a() == 1.5
        assert mod.b() == 2.5
        assert mod.c() == 3.5

    def test_f32_repr(self):
        mod = self.compile("""
        def repr_f32(x: f32) -> str:
            return repr(x)

        def str_f32(x: f32) -> str:
            return str(x)
        """)
        # Keep the decimal point so an integral float is distinguishable from an int.
        assert mod.repr_f32(1.0) == "1.0"
        # Negative zero has a distinct IEEE-754 sign bit which CPython preserves.
        assert mod.repr_f32(-0.0) == "-0.0"
        # Match CPython's canonical lowercase spelling for NaN.
        assert mod.repr_f32(float("nan")) == "nan"
        # Ryu spells this "Infinity"; SPy follows CPython's lowercase spelling.
        assert mod.repr_f32(float("inf")) == "inf"
        # Preserve the sign while normalizing Ryu's "-Infinity" spelling.
        assert mod.repr_f32(float("-inf")) == "-inf"
        # Normalize Ryu's "1E20" to CPython's lowercase, explicitly signed exponent.
        assert mod.repr_f32(1e20) == "1e+20"
        # CPython pads a single-digit negative exponent to two digits.
        assert mod.repr_f32(1e-5) == "1e-05"
        # CPython switches to fixed notation at exponent -4.
        assert mod.repr_f32(1e-4) == "0.0001"
        # CPython keeps exponent 15 in fixed notation.
        assert mod.repr_f32(1e15) == "1000000000000000.0"
        # CPython switches to scientific notation at exponent 16.
        assert mod.repr_f32(1e16) == "1e+16"
        # str and repr share one formatter, including for values needing more digits.
        x = 0.5000000596046448
        assert mod.str_f32(x) == mod.repr_f32(x)

    def test_f32_repr_roundtrip(self):
        mod = self.compile("""
        def repr_f32(x: f32) -> str:
            return repr(x)

        def f32_equal(x: f32, y: f32) -> bool:
            return x == y
        """)
        # This is the f32 with bits 0x3f000001. Unlike 3.14, it needs more
        # digits for its shortest round-trippable representation.
        x = 0.5000000596046448
        s = mod.repr_f32(x)
        assert s == "0.50000006"
        # f32 has no string-parsing constructor yet, so parse with Python and
        # compare after both arguments have been converted to f32.
        assert mod.f32_equal(x, float(s))

        # The smallest positive subnormal still needs a shortest representation
        # which survives decimal parsing.
        x = 1.401298464324817e-45
        s = mod.repr_f32(x)
        assert s == "1e-45"
        assert mod.f32_equal(x, float(s))

        # The largest finite f32 exercises the other end of Ryu's exponent and
        # significant-digit range.
        x = 3.4028234663852886e38
        s = mod.repr_f32(x)
        assert s == "3.4028235e+38"
        assert mod.f32_equal(x, float(s))

    def test_f64_repr(self):
        mod = self.compile("""
        def repr_f64(x: f64) -> str:
            return repr(x)

        def str_f64(x: f64) -> str:
            return str(x)
        """)
        assert mod.repr_f64(1.0) == "1.0"
        assert mod.repr_f64(-0.0) == "-0.0"
        assert mod.repr_f64(float("nan")) == "nan"
        assert mod.repr_f64(float("inf")) == "inf"
        assert mod.repr_f64(float("-inf")) == "-inf"
        assert mod.repr_f64(1e-5) == "1e-05"
        assert mod.repr_f64(1e-4) == "0.0001"
        assert mod.repr_f64(1e15) == "1000000000000000.0"
        assert mod.repr_f64(1e16) == "1e+16"
        x = 1.0000000000000002
        assert mod.str_f64(x) == mod.repr_f64(x)

    def test_f64_repr_roundtrip(self):
        mod = self.compile("""
        def repr_f64(x: f64) -> str:
            return repr(x)
        """)

        def assert_roundtrip(x: float, expected: str):
            result = mod.repr_f64(x)
            assert result == expected
            assert float(result) == x

        assert_roundtrip(1.0000000000000002, "1.0000000000000002")
        assert_roundtrip(5e-324, "5e-324")
        assert_roundtrip(1.7976931348623157e308, "1.7976931348623157e+308")

    def test_f32_inf_const(self):
        mod = self.compile("""
        def positive_inf() -> f32:
            largest = f32(3.4028234663852886e38)
            return largest + largest
        """)
        assert mod.positive_inf() == float("inf")

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

    def test_mixed_types(self, float_type):
        mod = self.compile(f"""
        T = {float_type}
        def add(x: T, y: i32) -> T: return x + y
        def sub(x: i32, y: T) -> T: return x - y
        def mul(x: T, y: i32) -> T: return x * y
        def div(x: i32, y: T) -> T: return x / y
        """)
        assert mod.add(1.5, 2) == 3.5
        assert mod.sub(10, 0.5) == 9.5
        assert mod.mul(1.5, 2) == 3.0
        assert mod.div(10, 0.5) == 20.0

    def test_float_to_all_ints_conversion(self):
        mod = self.compile("""
        def add_i8(x: f64, y: i8) -> f64: return x + y
        def add_u8(x: f64, y: u8) -> f64: return x + y
        def add_u32(x: f64, y: u32) -> f64: return x + y
        def add_f32(x: f64, y: f32) -> f64: return x + y
        """)
        assert mod.add_i8(1.5, 2) == 3.5
        assert mod.add_u8(1.5, 2) == 3.5
        assert mod.add_u32(1.5, 2) == 3.5
        assert mod.add_f32(1.5, 2.0) == 3.5

    def test_pow(self, float_type):
        mod = self.compile(f"""
        T = {float_type}
        def pow(x: T, y: T) -> T:
            return x ** y
        """)
        assert mod.pow(2.0, 3.0) == 8.0
        assert mod.pow(3.0, 2.0) == 9.0
        assert mod.pow(5.0, 0.0) == 1.0
        assert math.isclose(mod.pow(2.0, 0.5), 1.4142135623730951, rel_tol=1e-6)
        assert math.isclose(mod.pow(4.0, 0.5), 2.0, rel_tol=1e-6)
        assert math.isclose(mod.pow(2.0, -1.0), 0.5, rel_tol=1e-6)

    def test_pow_negative_base(self, float_type):
        mod = self.compile(f"""
        T = {float_type}
        def pow(x: T, y: T) -> T:
            return x ** y
        """)
        assert math.isclose(mod.pow(-2.0, 3.0), -8.0, rel_tol=1e-6)
        assert math.isclose(mod.pow(-2.0, 2.0), 4.0, rel_tol=1e-6)
        assert math.isclose(mod.pow(-1.0, 4.0), 1.0, rel_tol=1e-6)
        assert math.isclose(mod.pow(-2.0, -1.0), -0.5, rel_tol=1e-6)
        assert math.isclose(mod.pow(-2.0, -2.0), 0.25, rel_tol=1e-6)

    def test_pow_negative_base_fractional_exp_raises(self, float_type):
        mod = self.compile(f"""
        T = {float_type}
        def pow(x: T, y: T) -> T:
            return x ** y
        """)
        with SPyError.raises("W_ValueError", match="math domain error"):
            mod.pow(-5.0, 0.5)
        with SPyError.raises("W_ValueError", match="math domain error"):
            mod.pow(-2.0, 1.5)

    def test_pow_zero_negative_exp_raises(self, float_type):
        mod = self.compile(f"""
        T = {float_type}
        def pow(x: T, y: T) -> T:
            return x ** y
        """)
        with SPyError.raises(
            "W_ZeroDivisionError", match="0.0 cannot be raised to a negative power"
        ):
            mod.pow(0.0, -1.0)
        with SPyError.raises(
            "W_ZeroDivisionError", match="0.0 cannot be raised to a negative power"
        ):
            mod.pow(0.0, -2.0)

    def test_pow_base_between_zero_and_one(self, float_type):
        mod = self.compile(f"""
        T = {float_type}
        def pow(x: T, y: T) -> T:
            return x ** y
        """)
        assert math.isclose(mod.pow(0.5, 2.0), 0.25, rel_tol=1e-6)
        assert math.isclose(mod.pow(0.5, -1.0), 2.0, rel_tol=1e-6)
        assert math.isclose(mod.pow(0.1, 2.0), 0.01, rel_tol=1e-5)
        assert math.isclose(mod.pow(0.5, 0.5), 0.7071067811865476, rel_tol=1e-6)

    def test_explicit_conversion(self):
        mod = self.compile("""
        def i32_to_f64(x: i32) -> f64: return f64(x)
        def f32_to_f64(x: f32) -> f64: return f64(x)
        def f64_to_i32(x: f64) -> i32: return i32(x)
        def f32_to_i32(x: f32) -> i32: return i32(x)
        def i32_to_f32(x: i32) -> f32: return f32(x)
        def f64_to_f32(x: f64) -> f32: return f32(x)
        """)
        assert mod.i32_to_f64(42) == 42.0
        assert mod.f32_to_f64(42.0) == 42.0
        assert mod.f64_to_i32(42.0) == 42
        assert mod.f32_to_i32(42.0) == 42
        assert mod.i32_to_f32(42) == 42.0
        assert mod.f64_to_f32(42.5) == 42.5

    def test_prebuilt_const(self):
        src = """
        def foo() -> f64:
            x: f32 = 1.25
            y: f64 = 2.5
            return x + y
        """
        mod = self.compile(src)
        assert mod.foo() == 3.75
