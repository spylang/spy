import pytest
from spy.vm.b import B
from spy.tests.support import CompilerTest, only_interp

# Eventually we want to remove the @only_interp, but for now the C backend
# doesn't support lists
@only_interp
class TestTuple(CompilerTest):

    def test_literal(self):
        mod = self.compile(
        """
        def foo() -> dynamic:
            return 1, 2, 'hello'
        """)
        tup = mod.foo()
        assert tup == (1, 2, 'hello')

    def test_unpacking(self):
        mod = self.compile(
        """
        def make_tuple() -> dynamic:
            return 1, 2, 'hello'

        def foo() -> i32:
            a, b, c = make_tuple()
            return a + b
        """)
        x = mod.foo()
        assert x == 3
