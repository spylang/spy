#-*- encoding: utf-8 -*-

import pytest
from spy.tests.support import CompilerTest, skip_backends, no_backend

class TestFloat(CompilerTest):

    def test_literal(self):
        mod = self.compile(
        """
        def foo() -> f64:
            return 12.3
        """)
        assert mod.foo() == 12.3
