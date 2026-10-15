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
        from math import sqrt  # , cos, sin, tan, log, log10, exp
        # from math import acos, asin, atan, atan2, ceil, floor, fabs

        def constants() -> tuple[f64, f64, f64]:
            return pi, tau, e

        def f_sqrt(x: f64) -> f64:
            return sqrt(x)
        """
        mod = self.compile(src)
        assert mod.constants() == (math.pi, math.tau, math.e)
        assert mod.f_sqrt(4.0) == 2.0

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
