import math

import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, only_interp


@pytest.fixture(params=["complex128"])
def complex_type(request):
    return request.param


@only_interp
class TestComplex(CompilerTest):
    def test_literal(self):
        mod = self.compile("""
        def foo() -> complex128:
            return 12.3j
        """)
        assert mod.foo() == 12.3j
