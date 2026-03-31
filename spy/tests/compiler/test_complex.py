from math import isinf, isnan

import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest


@pytest.fixture(params=["complex128"])
def complex_type(request):
    return request.param


class TestComplex(CompilerTest):
    def test_literal(self):
        mod = self.compile("""
        def foo() -> complex128:
            return 12.3j
        """)
        assert mod.foo() == 12.3j

    def test_BinOp(self, complex_type):
        mod = self.compile(f"""
        T = {complex_type}
        def add(x: T, y: T) -> T:      return x + y
        def sub(x: T, y: T) -> T:      return x - y
        def mul(x: T, y: T) -> T:      return x * y
        def div(x: T, y: T) -> T:      return x / y
        def neg(x: T) -> T:            return -x
        """)
        assert mod.add(1.5j, 2.6j) == 4.1j
        assert mod.sub(1.5j, 0.2j) == 1.3j
        assert mod.mul(1.5j, 0.5j) == -0.75 + 0j
        assert mod.div(1.5j, 2.0j) == 0.75 + 0j
        assert mod.neg(1 - 2.5j) == -1 + 2.5j

    def test_CompareOp(self, complex_type):
        mod = self.compile(f"""
        T = {complex_type}
        def cmp_eq (x: T, y: T) -> bool: return x == y
        def cmp_neq(x: T, y: T) -> bool: return x != y
        """)
        assert mod.cmp_eq(5.1j, 5.1j) is True
        assert mod.cmp_eq(5.1j, 6.2j) is False
        assert mod.cmp_neq(5.1j, 5.1j) is False
        assert mod.cmp_neq(5.1j, 6.2j) is True

    def test_zero_division_error(self, complex_type):
        mod = self.compile(f"""
        T = {complex_type}
        def div(x: T, y: T) -> T:      return x / y
        """)
        with SPyError.raises("W_ZeroDivisionError", match="complex division by zero"):
            mod.div(1.5j, 0j)

    def test_attributes_and_methods(self, complex_type):
        mod = self.compile(f"""
        T = {complex_type}
        def real(x: T) -> f64:         return x.real
        def imag(x: T) -> f64:         return x.imag
        def conj(x: T) -> T:           return x.conjugate()
        """)
        assert mod.real(2 + 8j) == 2.0
        assert mod.imag(2 + 8j) == 8.0
        assert mod.conj(2 + 8j) == 2 - 8j

    def test_mixed_types(self, complex_type):
        mod = self.compile(f"""
        T = {complex_type}
        def add_int(x: T, y: i32) -> T: return x + y
        def add_float(x: T, y: f64) -> T: return x + y
        def sub_int(x: i32, y: T) -> T: return x - y
        def sub_float(x: f64, y: T) -> T: return x - y
        def mul_int(x: T, y: i32) -> T: return x * y
        def mul_float(x: T, y: f64) -> T: return x * y
        def div_int(x: i32, y: T) -> T: return x / y
        def div_float(x: f64, y: T) -> T: return x / y
        """)
        assert mod.add_int(1.5j, 2) == 2 + 1.5j
        assert mod.add_float(1.5j, 2.0) == 2 + 1.5j
        assert mod.sub_int(10, 0.5j) == 10 - 0.5j
        assert mod.sub_float(10.0, 0.5j) == 10 - 0.5j
        assert mod.mul_int(1.5j, 2) == 3j
        assert mod.mul_float(1.5j, 2.0) == 3j
        assert mod.div_int(10, 0.5j) == -20.0j
        assert mod.div_float(10.0, 0.5j) == -20.0j

    def test_explicit_conversion(self, complex_type):
        mod = self.compile(f"""
        T = {complex_type}
        def str_to_complex(x: str) -> T:     return T(x)
        def i32_to_complex(x: i32) -> T:     return T(x)
        def f64_to_complex(x: f64) -> T:     return T(x)
        """)
        assert mod.str_to_complex("5.1") == 5.1 + 0j
        assert mod.i32_to_complex(5) == 5 + 0j
        assert mod.f64_to_complex(5.1) == 5.1 + 0j

    def test_str_parsing_conversion(self, complex_type):
        mod = self.compile(f"""
        T = {complex_type}
        def str_to_complex(x: str) -> T:     return T(x)
        """)
        assert mod.str_to_complex("+1.23") == 1.23 + 0j
        assert mod.str_to_complex("-4.5j") == -4.5j
        assert mod.str_to_complex("-1.23+4.5j") == -1.23 + 4.5j
        assert mod.str_to_complex("\t( -1.23+4.5J )\n") == -1.23 + 4.5j
        for str_arg in (
            " ",
            "(",
            "  )",
            " (   ) ",
            " ( -1.23+4.5j  } ",
            "-4.5j+1.23",
            "1 + 2j",
            "-1.23*4.5j",
        ):
            with SPyError.raises(
                "W_ValueError", match=r"complex\(\) arg is a malformed string"
            ):
                mod.str_to_complex(str_arg)
        c = mod.str_to_complex("-Infinity+NaNj")
        assert isinf(c.real)
        assert isnan(c.imag)

    def test_explicit_conv_two_params(self, complex_type):
        mod = self.compile(f"""
        T = {complex_type}
        def i32_to_complex(x: i32, y: i32) -> T:     return T(x, y)
        def f64_to_complex(x: f64, y: f64) -> T:     return T(x, y)
        """)
        assert mod.i32_to_complex(5, 6) == 5 + 6j
        assert mod.f64_to_complex(5.1, 6.2) == 5.1 + 6.2j
