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
