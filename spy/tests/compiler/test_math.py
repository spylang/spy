import math
import pytest
from spy.errors import SPyError
from spy.tests.support import CompilerTest, skip_backends, no_backend

class TestMath(CompilerTest):

    def test_sqrt(self):
        mod = self.compile(
        """
        from math import sqrt

        def foo(x: f64) -> f64:
            return sqrt(x)
        """)
        assert mod.foo(64.0) == 8
        assert mod.foo(2.0) == math.sqrt(2)

    def test_constants(self):
        mod = self.compile(
        """
        from math import pi, e, tau

        def get_pi() -> f64:
            return pi

        def get_e() -> f64:
            return e

        def get_tau() -> f64:
            return tau
        """)
        assert mod.get_pi() == math.pi
        assert mod.get_e() == math.e
        assert mod.get_tau() == math.tau

    def test_cos(self):
        mod = self.compile(
        """
        from math import cos

        def foo(x: f64) -> f64:
            return cos(x)
        """)
        assert mod.foo(0.0) == 1.0
        assert mod.foo(math.pi) == -1.0

    def test_sin(self):
        mod = self.compile(
        """
        from math import sin

        def foo(x: f64) -> f64:
            return sin(x)
        """)
        assert mod.foo(0.0) == 0.0
        assert abs(mod.foo(math.pi/2) - 1.0) < 1e-10

    def test_tan(self):
        mod = self.compile(
        """
        from math import tan

        def foo(x: f64) -> f64:
            return tan(x)
        """)
        assert mod.foo(0.0) == 0.0
        assert abs(mod.foo(math.pi/4) - 1.0) < 1e-10

    def test_log(self):
        mod = self.compile(
        """
        from math import log

        def foo(x: f64) -> f64:
            return log(x)
        """)
        assert mod.foo(1.0) == 0.0
        assert mod.foo(math.e) == 1.0

    def test_log10(self):
        mod = self.compile(
        """
        from math import log10

        def foo(x: f64) -> f64:
            return log10(x)
        """)
        assert mod.foo(1.0) == 0.0
        assert mod.foo(10.0) == 1.0

    def test_exp(self):
        mod = self.compile(
        """
        from math import exp

        def foo(x: f64) -> f64:
            return exp(x)
        """)
        assert mod.foo(0.0) == 1.0
        assert mod.foo(1.0) == math.e

    def test_acos(self):
        mod = self.compile(
        """
        from math import acos

        def foo(x: f64) -> f64:
            return acos(x)
        """)
        assert mod.foo(1.0) == 0.0
        assert abs(mod.foo(0.0) - math.pi/2) < 1e-10

    def test_asin(self):
        mod = self.compile(
        """
        from math import asin

        def foo(x: f64) -> f64:
            return asin(x)
        """)
        assert mod.foo(0.0) == 0.0
        assert abs(mod.foo(1.0) - math.pi/2) < 1e-10

    def test_atan(self):
        mod = self.compile(
        """
        from math import atan

        def foo(x: f64) -> f64:
            return atan(x)
        """)
        assert mod.foo(0.0) == 0.0
        assert abs(mod.foo(1.0) - math.pi/4) < 1e-10

    def test_atan2(self):
        mod = self.compile(
        """
        from math import atan2

        def foo(y: f64, x: f64) -> f64:
            return atan2(y, x)
        """)
        assert mod.foo(0.0, 1.0) == 0.0
        assert abs(mod.foo(1.0, 1.0) - math.pi/4) < 1e-10

    def test_ceil(self):
        mod = self.compile(
        """
        from math import ceil

        def foo(x: f64) -> f64:
            return ceil(x)
        """)
        assert mod.foo(1.0) == 1.0
        assert mod.foo(1.3) == 2.0
        assert mod.foo(-1.7) == -1.0

    def test_floor(self):
        mod = self.compile(
        """
        from math import floor

        def foo(x: f64) -> f64:
            return floor(x)
        """)
        assert mod.foo(1.0) == 1.0
        assert mod.foo(1.3) == 1.0
        assert mod.foo(-1.7) == -2.0

    def test_pow(self):
        mod = self.compile(
        """
        from math import pow

        def foo(x: f64, y: f64) -> f64:
            return pow(x, y)
        """)
        assert mod.foo(2.0, 3.0) == 8.0
        assert mod.foo(10.0, 2.0) == 100.0
        assert mod.foo(4.0, 0.5) == 2.0

    def test_fabs(self):
        mod = self.compile(
        """
        from math import fabs

        def foo(x: f64) -> f64:
            return fabs(x)
        """)
        assert mod.foo(3.5) == 3.5
        assert mod.foo(-3.5) == 3.5
        assert mod.foo(0.0) == 0.0
