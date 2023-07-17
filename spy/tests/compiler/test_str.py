import pytest
from spy.tests.support import CompilerTest, skip_backends, no_backend

class TestStr(CompilerTest):

    def test_literal(self):
        mod = self.compile(
        """
        def foo() -> str:
            return 'hello'
        """)
        assert mod.foo() == 'hello'
