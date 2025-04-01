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
