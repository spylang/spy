"""
Tests for the ** (power) operator.
"""

import pytest

from spy.tests.support import CompilerTest


@pytest.fixture(params=["i32", "u32", "i8", "u8"])
def int_type(request):
    return request.param


class TestPow(CompilerTest):
    """Test the ** (power) operator for various numeric types."""

    def test_pow_basic(self, int_type):
        """Test basic power operations with integer types."""
        mod = self.compile(f"""
        T = {int_type}
        def pow(x: T, y: T) -> T:
            return x ** y
        """)
        assert mod.pow(2, 3) == 8
        assert mod.pow(3, 2) == 9
        assert mod.pow(5, 0) == 1
        assert mod.pow(10, 2) == 100
        assert mod.pow(1, 100) == 1
        assert mod.pow(42, 1) == 42

    def test_pow_zero_base(self, int_type):
        """Test power with zero base."""
        mod = self.compile(f"""
        T = {int_type}
        def pow(x: T, y: T) -> T:
            return x ** y
        """)
        assert mod.pow(0, 0) == 1  # 0**0 is defined as 1 in Python
        assert mod.pow(0, 1) == 0
        assert mod.pow(0, 5) == 0

    def test_pow_negative_base(self, int_type):
        """Test power with negative base (only for signed types)."""
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

    def test_f64_pow(self):
        """Test power operations with f64."""
        mod = self.compile("""
        def pow(x: f64, y: f64) -> f64:
            return x ** y
        """)
        assert mod.pow(2.0, 3.0) == 8.0
        assert mod.pow(3.0, 2.0) == 9.0
        assert mod.pow(5.0, 0.0) == 1.0
        assert mod.pow(10.0, 2.0) == 100.0
        assert abs(mod.pow(2.0, 0.5) - 1.4142135623730951) < 1e-10  # sqrt(2)
        assert abs(mod.pow(4.0, 0.5) - 2.0) < 1e-10  # sqrt(4)

    def test_f64_pow_negative_exponent(self):
        """Test power with negative exponents."""
        mod = self.compile("""
        def pow(x: f64, y: f64) -> f64:
            return x ** y
        """)
        assert abs(mod.pow(2.0, -1.0) - 0.5) < 1e-10
        assert abs(mod.pow(10.0, -2.0) - 0.01) < 1e-10
        assert abs(mod.pow(4.0, -0.5) - 0.5) < 1e-10  # 1/sqrt(4)

    def test_mixed_int_float(self):
        """Test power with mixed i32 and f64 types."""
        mod = self.compile("""
        def pow_if(x: i32, y: f64) -> f64:
            return x ** y
        def pow_fi(x: f64, y: i32) -> f64:
            return x ** y
        """)
        assert abs(mod.pow_if(2, 3.0) - 8.0) < 1e-10
        assert abs(mod.pow_fi(2.0, 3) - 8.0) < 1e-10
        assert abs(mod.pow_if(4, 0.5) - 2.0) < 1e-10

    def test_pow_in_expression(self):
        """Test power operator in complex expressions."""
        mod = self.compile("""
        def expr1(x: i32) -> i32:
            return 2 ** x + 1
        def expr2(x: i32, y: i32) -> i32:
            return x ** 2 + y ** 2
        def expr3(x: i32) -> i32:
            return (x + 1) ** 2
        """)
        assert mod.expr1(3) == 9  # 2**3 + 1 = 8 + 1
        assert mod.expr2(3, 4) == 25  # 3**2 + 4**2 = 9 + 16
        assert mod.expr3(4) == 25  # (4+1)**2 = 25
