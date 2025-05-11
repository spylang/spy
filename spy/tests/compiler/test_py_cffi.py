import pytest
from spy.tests.support import CompilerTest, skip_backends, only_py_cffi

@only_py_cffi
class TestPyCFFI(CompilerTest):

    def test_simple(self):
        mod = self.compile(
        """
        def add(x: i32, y: i32) -> i32:
            return x + y
        """)
        # XXX: this is WIP, we want to generate also 'test.py' which
        # automatically maps FQN spy names into non-qualified names
        assert mod.pymod.lib.spy_test_add(4, 6) == 10
