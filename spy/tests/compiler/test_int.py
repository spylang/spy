import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest


@pytest.fixture(params=["i32", "u32", "i8", "u8"])
def int_type(request):
    return request.param


class TestInt(CompilerTest):
    def test_i8_conversion(self):
        mod = self.compile("""
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

    def test_u8_conversion(self):
        mod = self.compile("""
        def foo(x: i32) -> u8:
            return x

        def bar(x: u8) -> i32:
            return x
        """)
        assert mod.foo(42) == 42
        assert mod.foo(256 + 10) == 10
        assert mod.bar(42) == 42
        assert mod.bar(-1) == 255

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
        if int_type in ("u8", "u32"):
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
                mod.neg(-5)
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
        }
        too_big, too_small = limits[int_type]
        with SPyError.raises("W_OverflowError", match="out of range"):
            mod.foo(too_big)
        with SPyError.raises("W_OverflowError", match="out of range"):
            mod.foo(too_small)
