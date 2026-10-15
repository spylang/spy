import math

from spy.tests.support import CompilerTest, expect_errors, only_interp


class TestMath(CompilerTest):
    """This tests the SPy module stdlib/math.spy and its metafuncs.

    The concrete functions (defined in spy/vm/modules/_math.py and
    spy/libspy/include/spy/math.h) are tested in
    spy/tests/compiler/test__math.py.
    """

    def test_float(self):
        src = """
        from math import pi, tau, e
        from math import sqrt, cos, sin, tan, log, log10, exp
        from math import acos, asin, atan, atan2, ceil, floor, pow, fabs

        def constants() -> tuple[f64, f64, f64]:
            return pi, tau, e

        def f_sqrt(x: f64) -> f64:
            return sqrt(x)

        def f_cos(x: f64) -> f64:
            return cos(x)

        def f_sin(x: f64) -> f64:
            return sin(x)

        def f_tan(x: f64) -> f64:
            return tan(x)

        def f_log(x: f64) -> f64:
            return log(x)

        def f_log10(x: f64) -> f64:
            return log10(x)

        def f_exp(x: f64) -> f64:
            return exp(x)

        def f_acos(x: f64) -> f64:
            return acos(x)

        def f_asin(x: f64) -> f64:
            return asin(x)

        def f_atan(x: f64) -> f64:
            return atan(x)

        def f_atan2(y: f64, x: f64) -> f64:
            return atan2(y, x)

        def f_ceil(x: f64) -> f64:
            return ceil(x)

        def f_floor(x: f64) -> f64:
            return floor(x)

        def f_pow(x: f64, y: f64) -> f64:
            return pow(x, y)

        def f_fabs(x: f64) -> f64:
            return fabs(x)
        """
        mod = self.compile(src)
        assert mod.constants() == (math.pi, math.tau, math.e)
        assert mod.f_sqrt(4.0) == 2.0
        assert mod.f_cos(0.0) == 1.0
        assert mod.f_sin(0.0) == 0.0
        assert mod.f_tan(0.0) == 0.0
        assert mod.f_log(1.0) == 0.0
        assert mod.f_log10(100.0) == 2.0
        assert mod.f_exp(0.0) == 1.0
        assert mod.f_acos(1.0) == 0.0
        assert mod.f_asin(0.0) == 0.0
        assert mod.f_atan(0.0) == 0.0
        assert mod.f_atan2(0.0, 1.0) == 0.0
        assert mod.f_ceil(1.5) == 2.0
        assert mod.f_floor(1.5) == 1.0
        assert mod.f_pow(2.0, 3.0) == 8.0
        assert mod.f_fabs(-1.5) == 1.5

    @only_interp
    def test_sqrt_unsupported_type(self):
        src = """
        from math import sqrt

        def foo() -> None:
            print(sqrt(4))
        """
        errors = expect_errors(
            "`sqrt` does not support arguments of type `i32`",
            ("this is `i32`", "4"),
            ("metafunc defined here", "def sqrt(m_x):"),
        )
        self.compile_raises(src, "foo", errors)
