from math import isclose, isnan

import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest


@pytest.fixture(params=["i32", "u32", "i8", "u8"])
def int_type(request):
    return request.param


class TestUnsafeIntDiv(CompilerTest):
    """
    NOTE: unchecked_div & co. are actually unchecked only in compiled SPY_RELEASE
    mode.

    In interp mode and compiled SPY_DEBUG mode, they still panic in case of
    divide-by-zero. CompilerTest runs in debug mode, that's why we still test the panic
    here.
    """

    def test_unchecked_div(self, int_type):
        mod = self.compile(f"""
        from unsafe import unchecked_div
        T = {int_type}
        def div(x: T, y: T) -> f64: return unchecked_div(x, y)
        """)
        assert mod.div(7, 2) == 3.5
        assert mod.div(120, 16) == 7.5
        assert mod.div(45, 60) == 0.75

    def test_unchecked_floordiv(self, int_type):
        mod = self.compile(f"""
        from unsafe import unchecked_floordiv
        T = {int_type}
        def floordiv(x: T, y: T) -> T: return unchecked_floordiv(x, y)
        """)
        assert mod.floordiv(7, 2) == 3
        assert mod.floordiv(120, 16) == 7
        assert mod.floordiv(45, 60) == 0

    def test_unchecked_mod(self, int_type):
        mod = self.compile(f"""
        from unsafe import unchecked_mod
        T = {int_type}
        def mod(x: T, y: T) -> T: return unchecked_mod(x, y)
        """)
        assert mod.mod(10, 3) == 1
        assert mod.mod(122, 2) == 0
        assert mod.mod(116, 5) == 1

    def test_floordiv_mod_mixed_signs(self, int_type):
        if int_type in ("u8", "u32"):
            pytest.skip("Skipping for negative operands in floordiv test")

        mod = self.compile(f"""
        from unsafe import unchecked_floordiv, unchecked_mod
        T = {int_type}
        def floordiv(x: T, y: T) -> T: return unchecked_floordiv(x, y)
        def mod(x: T, y: T) -> T: return unchecked_mod(x, y)
        """)
        assert mod.floordiv(7, 3) == 2
        assert mod.floordiv(-7, 3) == -3
        assert mod.floordiv(7, -3) == -3
        assert mod.floordiv(-7, -3) == 2
        assert mod.mod(7, 3) == 1
        assert mod.mod(-7, 3) == 2
        assert mod.mod(7, -3) == -2
        assert mod.mod(-7, -3) == -1

    def test_spy_zero_division_unchecked(self, int_type):
        mod = self.compile(f"""
        from unsafe import unchecked_div, unchecked_floordiv, unchecked_mod
        T = {int_type}
        def div(x: T, y: T) -> f64: return unchecked_div(x, y)
        def floordiv(x: T, y: T) -> T: return unchecked_floordiv(x, y)
        def mod(x: T, y: T) -> T: return unchecked_mod(x, y)
        """)
        with SPyError.raises("W_PanicError", match="division by zero"):
            mod.div(11, 0)

        with SPyError.raises(
            "W_PanicError", match="integer division or modulo by zero"
        ):
            mod.floordiv(11, 0)

        with SPyError.raises("W_PanicError", match="integer modulo by zero"):
            mod.mod(10, 0)


@pytest.fixture(params=["f64", "f32"])
def float_type(request):
    return request.param


class TestUnsafeFloatDiv(CompilerTest):
    def test_unchecked_div(self, float_type):
        mod = self.compile(f"""
        from unsafe import unchecked_div
        T = {float_type}
        def div(x: T, y: T) -> T: return unchecked_div(x, y)
        """)
        assert mod.div(1.5, 2.0) == 0.75
        assert mod.div(11.0, 2.0) == 5.5
        assert isclose(
            mod.div(500.000034, 45.000034), 500.000034 / 45.000034, rel_tol=1e-6
        )

    def test_ieee754_div(self):
        mod = self.compile("""
        from unsafe import ieee754_div
        def div(x: f64, y: f64) -> f64: return ieee754_div(x, y)
        """)
        assert mod.div(1.5, 2.0) == 0.75
        assert mod.div(11.0, 2.0) == 5.5
        assert mod.div(500.000034, 45.000034) == 500.000034 / 45.000034

    def test_unchecked_floordiv(self, float_type):
        mod = self.compile(f"""
        from unsafe import unchecked_floordiv
        T = {float_type}
        def floordiv(x: T, y: T) -> T: return unchecked_floordiv(x, y)
        """)
        assert mod.floordiv(1.5, 2.0) == 0.0
        assert mod.floordiv(11.0, 2.0) == 5.0
        assert mod.floordiv(500.000034, 45.000034) == 500.000034 // 45.000034

    def test_unchecked_mod(self, float_type):
        mod = self.compile(f"""
        from unsafe import unchecked_mod
        T = {float_type}
        def mod(x: T, y: T) -> T: return unchecked_mod(x, y)
        """)
        assert mod.mod(10.5, 2.5) == 0.5
        assert mod.mod(11.0, 2.0) == 1.0
        assert isclose(
            mod.mod(500.000034, 45.000034), 500.000034 % 45.000034, rel_tol=1e-5
        )

    def test_ieee754_zero_div(self, float_type):
        mod = self.compile(f"""
        from unsafe import ieee754_div
        T = {float_type}
        def div(x: T, y: T) -> T: return ieee754_div(x, y)
        """)
        assert mod.div(1.5, 0.0) == float("inf")
        assert mod.div(-1.5, 0.0) == float("-inf")
        assert isnan(mod.div(0.0, 0.0))

    def test_spy_zero_division_unchecked(self, float_type):
        mod = self.compile(f"""
        from unsafe import unchecked_div, unchecked_floordiv, unchecked_mod
        T = {float_type}
        def div(x: T, y: T) -> T: return unchecked_div(x, y)
        def floordiv(x: T, y: T) -> T: return unchecked_floordiv(x, y)
        def mod(x: T, y: T) -> T: return unchecked_mod(x, y)
        """)
        with SPyError.raises("W_PanicError", match="float division by zero"):
            mod.div(1.5, 0.0)

        with SPyError.raises("W_PanicError", match="float floor division by zero"):
            mod.floordiv(10.0, 0.0)

        with SPyError.raises("W_PanicError", match="float modulo by zero"):
            mod.mod(10.5, 0.0)

    def test_division_mixed_signs(self, float_type):
        mod = self.compile(f"""
        from unsafe import unchecked_floordiv, unchecked_mod
        T = {float_type}
        def floordiv(x: T, y: T) -> T: return unchecked_floordiv(x, y)
        def mod(x: T, y: T) -> T: return unchecked_mod(x, y)
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

    def test_division_mixed_types(self):
        mod = self.compile("""
        from unsafe import unchecked_div, unchecked_floordiv, unchecked_mod
        def div(x: i32, y: f64) -> f64: return unchecked_div(x, y)
        def div2(x: f64, y: i32) -> f64: return unchecked_div(x, y)
        def floordiv(x: i32, y: f64) -> f64: return unchecked_floordiv(x, y)
        def floordiv2(x: f64, y: i32) -> f64: return unchecked_floordiv(x, y)
        def mod(x: i32, y: f64) -> f64: return unchecked_mod(x, y)
        def mod2(x: f64, y: i32) -> f64: return unchecked_mod(x, y)
        """)
        assert mod.div(11, 2.0) == 5.5
        assert mod.div2(11.0, 2) == 5.5
        assert mod.floordiv(11, 2.0) == 5.0
        assert mod.floordiv2(11.0, 2) == 5.0
        assert mod.mod(11, 2.0) == 1.0
        assert mod.mod2(11.0, 2) == 1.0
