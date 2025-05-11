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
        breakpoint()
