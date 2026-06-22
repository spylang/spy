import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors, skip_backends


@pytest.fixture(params=["i32", "u32", "i8", "u8", "i64", "u64"])
def int_type(request):
    return request.param


@pytest.fixture(params=["i32", "i8", "i64"])
def signed_int_type(request):
    return request.param


class TestInt(CompilerTest):
    def test_i8_conversion(self):
        mod = self.compile("""
        def i32_to_i8_imp(x: i32) -> i8:
            return x

        def i8_to_i32_imp(x: i8) -> i32:
            return x

        def i32_to_i8_exp(x: i32) -> i8:
            return i8(x)

        def i8_to_i32_exp(x: i8) -> i32:
            return i32(x)

        def i8_from_lit_pos() -> i8:
            return i8(42)

        def i8_from_lit_neg() -> i8:
            return i8(-5)
        """)
        assert mod.i32_to_i8_imp(42) == 42
        assert mod.i32_to_i8_imp(128) == -128
        assert mod.i8_to_i32_imp(42) == 42
        assert mod.i8_to_i32_imp(-1) == -1
        assert mod.i8_to_i32_imp(128) == -128
        assert mod.i32_to_i8_exp(42) == 42
        assert mod.i32_to_i8_exp(128) == -128
        assert mod.i8_to_i32_exp(42) == 42
        assert mod.i8_to_i32_exp(-1) == -1
        assert mod.i8_from_lit_pos() == 42
        assert mod.i8_from_lit_neg() == -5

    def test_u8_conversion(self):
        mod = self.compile("""
        def i32_to_u8_imp(x: i32) -> u8:
            return x

        def u8_to_i32_imp(x: u8) -> i32:
            return x

        def i32_to_u8_exp(x: i32) -> u8:
            return u8(x)

        def u8_to_i32_exp(x: u8) -> i32:
            return i32(x)

        def u8_from_lit() -> u8:
            return u8(200)
        """)
        assert mod.i32_to_u8_imp(42) == 42
        assert mod.i32_to_u8_imp(256 + 10) == 10
        assert mod.u8_to_i32_imp(42) == 42
        assert mod.u8_to_i32_imp(-1) == 255
        assert mod.i32_to_u8_exp(42) == 42
        assert mod.i32_to_u8_exp(256) == 0
        assert mod.u8_to_i32_exp(255) == 255
        assert mod.u8_from_lit() == 200

    def test_u32_conversion(self):
        mod = self.compile("""
        def foo(x: i32) -> u32:
            return x

        def bar(x: u32) -> i32:
            return x
        """)
        MAX = 2**32
        assert mod.foo(42) == 42
        assert mod.foo(MAX + 10) == 10
        assert mod.bar(42) == 42
        assert mod.bar(-1) == -1

    def test_i64_conversion(self):
        mod = self.compile("""
        def i32_to_i64_imp(x: i32) -> i64:
            return x

        def i8_to_i64_imp(x: i8) -> i64:
            return x

        def u8_to_i64_imp(x: u8) -> i64:
            return x

        def u32_to_i64_imp(x: u32) -> i64:
            return x

        def i64_to_f64_imp(x: i64) -> f64:
            return x

        def i8_to_i64_exp(x: i8) -> i64:
            return i64(x)

        def u8_to_i64_exp(x: u8) -> i64:
            return i64(x)

        def i32_to_i64_exp(x: i32) -> i64:
            return i64(x)

        def u32_to_i64_exp(x: u32) -> i64:
            return i64(x)

        def f64_to_i64_exp(x: f64) -> i64:
            return i64(x)

        def f32_to_i64_exp(x: f32) -> i64:
            return i64(x)

        def u64_to_i64_exp(x: u64) -> i64:
            return i64(x)
        """)
        assert mod.i32_to_i64_imp(42) == 42
        assert mod.i32_to_i64_imp(-1) == -1
        assert mod.i8_to_i64_imp(-1) == -1
        assert mod.u8_to_i64_imp(255) == 255
        assert mod.u32_to_i64_imp(2**32 - 1) == 2**32 - 1
        assert mod.i64_to_f64_imp(42) == 42.0
        assert mod.i8_to_i64_exp(-1) == -1
        assert mod.u8_to_i64_exp(255) == 255
        assert mod.i32_to_i64_exp(-1) == -1
        assert mod.u32_to_i64_exp(2**32 - 1) == 2**32 - 1
        assert mod.f64_to_i64_exp(12.5) == 12
        assert mod.f64_to_i64_exp(float(2**63)) == 2**63 - 1
        assert mod.f64_to_i64_exp(float(-(2**63)) * 2) == -(2**63)
        assert mod.f64_to_i64_exp(float("nan")) == 0
        assert mod.f32_to_i64_exp(12.5) == 12
        assert mod.f32_to_i64_exp(float(2**63)) == 2**63 - 1
        assert mod.f32_to_i64_exp(float(-(2**63)) * 2) == -(2**63)
        assert mod.f32_to_i64_exp(float("nan")) == 0
        assert mod.u64_to_i64_exp(2**64 - 1) == -1

    def test_u64_conversion(self):
        mod = self.compile("""
        def u64_to_f64_imp(x: u64) -> f64:
            return x

        def i64_to_u64_exp(x: i64) -> u64:
            return u64(x)
        """)
        assert mod.u64_to_f64_imp(42) == 42.0
        assert mod.i64_to_u64_exp(-1) == 2**64 - 1

    def test_i64_u64_str(self):
        mod = self.compile("""
        def i64_str(x: i64) -> str:
            return str(x)

        def u64_str(x: u64) -> str:
            return str(x)
        """)
        assert mod.i64_str(-9223372036854775808) == "-9223372036854775808"
        assert mod.u64_str(18446744073709551615) == "18446744073709551615"

    def test_i64_u64_repr(self):
        mod = self.compile("""
        def i64_repr(x: i64) -> str:
            return repr(x)

        def u64_repr(x: u64) -> str:
            return repr(x)
        """)
        assert mod.i64_repr(-9223372036854775808) == "-9223372036854775808"
        assert mod.u64_repr(18446744073709551615) == "18446744073709551615"

    def test_i64_u64_spy_key(self):
        mod = self.compile("""
        @blue
        def fmt(x: i64, y: u64) -> str:
            return str(x) + ", " + str(y)

        def foo() -> str:
            return fmt(i64(1), u64(2))

        """)
        assert mod.foo() == "1, 2"

    def test_float_to_int(self):
        mod = self.compile("""
        def to_i32(x: f64) -> i32: return i32(x)
        """)
        MAX = 2**31 - 1
        assert mod.to_i32(12.5) == 12
        assert mod.to_i32(float(MAX * 2)) == MAX
        assert mod.to_i32(float("inf")) == MAX
        assert mod.to_i32(float("nan")) == 0

    def test_binop(self, int_type):
        mod = self.compile(f"""
        T = {int_type}
        def add(x: T, y: T) -> T:      return x + y
        def sub(x: T, y: T) -> T:      return x - y
        def mul(x: T, y: T) -> T:      return x * y
        def mod(x: T, y: T) -> T:      return x % y
        def div(x: T, y: T) -> f64:    return x / y
        def floordiv(x: T, y: T) -> T: return x // y
        """)
        assert mod.add(1, 2) == 3
        assert mod.sub(7, 3) == 4
        assert mod.mul(5, 6) == 30
        assert mod.mod(10, 3) == 1
        assert mod.div(11, 2) == 5.5
        assert mod.floordiv(11, 2) == 5

    def test_zero_division_error(self, int_type):
        mod = self.compile(f"""
        T = {int_type}
        def mod(x: T, y: T) -> T:      return x % y
        def div(x: T, y: T) -> f64:    return x / y
        def floordiv(x: T, y: T) -> T: return x // y
        """)
        with SPyError.raises("W_ZeroDivisionError", match="integer modulo by zero"):
            mod.mod(10, 0)
        with SPyError.raises("W_ZeroDivisionError", match="division by zero"):
            mod.div(11, 0)
        with SPyError.raises(
            "W_ZeroDivisionError", match="integer division or modulo by zero"
        ):
            mod.floordiv(11, 0)

    def test_division_mixed_signs(self, int_type):
        if int_type in ("u8", "u32", "u64"):
            pytest.skip("Skipping for negative operands in floordiv test")

        mod = self.compile(f"""
        T = {int_type}
        def floordiv(x: T, y: T) -> T: return x // y
        def mod(x: T, y: T) -> T: return x % y
        """)
        assert mod.floordiv(7, 3) == 2
        assert mod.floordiv(-7, 3) == -3
        assert mod.floordiv(7, -3) == -3
        assert mod.floordiv(-7, -3) == 2
        assert mod.mod(7, 3) == 1
        assert mod.mod(-7, 3) == 2
        assert mod.mod(7, -3) == -2
        assert mod.mod(-7, -3) == -1

    def test_neg(self, int_type):
        src = f"""
        T = {int_type}
        def neg(x: T) -> T:
            return -x
        """
        mod = self.compile(src, error_mode="lazy")
        #
        is_unsigned = int_type.startswith("u")
        if is_unsigned:
            with SPyError.raises("W_TypeError", match=f"cannot do -`{int_type}`"):
                mod.neg(5)
        else:
            assert mod.neg(-5) == 5

    def test_bitwise(self, int_type):
        mod = self.compile(f"""
        T = {int_type}
        def shl(x: T, y: T) -> T:   return x << y
        def shr(x: T, y: T) -> T:   return x >> y
        def b_and(x: T, y: T) -> T: return x & y
        def b_or(x: T, y: T) -> T:  return x | y
        def b_xor(x: T, y: T) -> T: return x ^ y
        """)
        assert mod.shl(2, 5) == 2 << 5
        assert mod.shr(32, 5) == 32 >> 5
        assert mod.b_and(7, 3) == 7 & 3
        assert mod.b_and(127, 7) == 127 & 7
        assert mod.b_or(127, 123) == 127 | 123
        assert mod.b_or(127, 0) == 127 | 0
        assert mod.b_xor(16, 15) == 16 ^ 15
        assert mod.b_xor(16, 0) == 16 ^ 0

    def test_pow(self, int_type):
        mod = self.compile(f"""
        T = {int_type}
        def pow(x: T, y: T) -> T:
            return x ** y
        """)
        assert mod.pow(2, 3) == 8
        assert mod.pow(3, 2) == 9
        assert mod.pow(5, 0) == 1
        assert mod.pow(10, 2) == 100
        assert mod.pow(0, 0) == 1
        assert mod.pow(0, 5) == 0

    def test_pow_negative_base(self, int_type):
        if int_type.startswith("u"):
            pytest.skip("Skipping negative base test for unsigned types")
        mod = self.compile(f"""
        T = {int_type}
        def pow(x: T, y: T) -> T:
            return x ** y
        """)
        assert mod.pow(-2, 3) == -8
        assert mod.pow(-2, 2) == 4
        assert mod.pow(-1, 5) == -1
        assert mod.pow(-1, 4) == 1

    def test_pow_zero_negative_exp_raises(self, signed_int_type):
        mod = self.compile(f"""
        T = {signed_int_type}
        def pow(x: T, y: T) -> T:
            return x ** y
        """)
        with SPyError.raises(
            "W_ZeroDivisionError", match="0 cannot be raised to a negative power"
        ):
            mod.pow(0, -1)

    def test_pow_negative_exponent_raises(self, signed_int_type):
        mod = self.compile(f"""
        T = {signed_int_type}
        def pow(x: T, y: T) -> T:
            return x ** y
        """)
        with SPyError.raises("W_ValueError", match="integer \\*\\* negative exponent"):
            mod.pow(2, -1)

    def test_pow_overflow_wraps(self):
        mod = self.compile("""
        def f(x: i32, y: i32) -> i32:
            return x ** y
        """)
        # 2**31 overflows i32 and wraps to i32::MIN (-2147483648)
        assert mod.f(2, 31) == -2147483648

    def test_cmp(self, int_type):
        mod = self.compile(f"""
        T = {int_type}
        def cmp_eq (x: T, y: T) -> bool: return x == y
        def cmp_neq(x: T, y: T) -> bool: return x != y
        def cmp_lt (x: T, y: T) -> bool: return x  < y
        def cmp_lte(x: T, y: T) -> bool: return x <= y
        def cmp_gt (x: T, y: T) -> bool: return x  > y
        def cmp_gte(x: T, y: T) -> bool: return x >= y
        """)
        assert mod.cmp_eq(5, 5) is True
        assert mod.cmp_eq(5, 6) is False

        assert mod.cmp_neq(5, 5) is False
        assert mod.cmp_neq(5, 6) is True

        assert mod.cmp_lt(5, 6) is True
        assert mod.cmp_lt(5, 5) is False
        assert mod.cmp_lt(6, 5) is False

        assert mod.cmp_lte(5, 6) is True
        assert mod.cmp_lte(5, 5) is True
        assert mod.cmp_lte(6, 5) is False

        assert mod.cmp_gt(5, 6) is False
        assert mod.cmp_gt(5, 5) is False
        assert mod.cmp_gt(6, 5) is True

        assert mod.cmp_gte(5, 6) is False
        assert mod.cmp_gte(5, 5) is True
        assert mod.cmp_gte(6, 5) is True

    def test_int_from_str(self, int_type):
        mod = self.compile(f"""
        T = {int_type}
        def foo(s: str) -> T:
            return T(s)
        """)
        assert mod.foo("0") == 0
        assert mod.foo("123") == 123
        if not int_type.startswith("u"):
            assert mod.foo("-42") == -42

    def test_int_from_str_invalid(self, int_type):
        mod = self.compile(f"""
        T = {int_type}
        def foo(s: str) -> T:
            return T(s)
        """)
        with SPyError.raises("W_ValueError", match="invalid literal for int()"):
            mod.foo("hello")

    def test_int_from_str_overflow(self, int_type):
        mod = self.compile(f"""
        T = {int_type}
        def foo(s: str) -> T:
            return T(s)
        """)
        limits = {
            "i32": ("2147483648", "-2147483649"),
            "u32": ("4294967296", "-1"),
            "i8": ("128", "-129"),
            "u8": ("256", "-1"),
            "i64": ("9223372036854775808", "-9223372036854775809"),
            "u64": ("18446744073709551616", "-1"),
        }
        too_big, too_small = limits[int_type]
        with SPyError.raises("W_OverflowError", match="out of range"):
            mod.foo(too_big)
        with SPyError.raises("W_OverflowError", match="out of range"):
            mod.foo(too_small)

    @skip_backends("C", reason="C parser uses strtoll and doesn't match int() yet")
    def test_int_from_str_advanced(self, int_type):
        # interp delegates to Python's int(), which accepts surrounding
        # whitespace and underscore separators. The C backend uses strtoll and
        # is stricter; we will align it in a future PR.
        mod = self.compile(f"""
        T = {int_type}
        def foo(s: str) -> T:
            return T(s)
        """)
        assert mod.foo("  42  ") == 42
        assert mod.foo("42\n") == 42
        assert mod.foo("+42") == 42
        assert mod.foo("1_2_3") == 123
        if not int_type.startswith("u"):
            assert mod.foo("  -5  ") == -5

    def test_int_literals(self):
        # a bare literal defaults to i32; explicitly-prefixed literals can hold
        # values bigger than i32
        mod = self.compile("""
        def bare() -> i32:
            return 42

        def big_i64() -> i64:
            return i64(2147483648)

        def big_u64() -> u64:
            return u64(9223372036854775808)
        """)
        assert mod.bare() == 42
        assert mod.big_i64() == 2147483648
        assert mod.big_u64() == 9223372036854775808

    def test_bare_literal_too_big_for_i32(self):
        # the default type of a bare literal is i32; a bigger literal is an
        # error suggesting the explicit i64()/u64() form
        src = """
        def foo() -> i64:
            return 2147483648
        """
        errors = expect_errors(
            "integer literal 2147483648 is out of range for i32; "
            "use i64(2147483648) or u64(2147483648) to get a 64-bit value",
            ("integer literal out of range", "2147483648"),
        )
        self.compile_raises(src, "foo", errors)
