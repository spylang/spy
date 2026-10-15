import math

from spy.tests.support import CompilerTest


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
