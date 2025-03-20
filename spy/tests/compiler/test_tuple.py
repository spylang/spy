import pytest
from spy.errors import SPyError
from spy.vm.b import B
from spy.tests.support import CompilerTest, only_interp, expect_errors

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

    def test_getitem(self):
        mod = self.compile(
        """
        def foo(i: i32) -> dynamic:
            tup = 1, 2, 'hello'
            return tup[i]
        """)
        x = mod.foo(0)
        assert x == 1
        y = mod.foo(2)
        assert y == 'hello'

    def test_unpacking(self):
        mod = self.compile(
        """
        def make_tuple() -> tuple:
            return 1, 2, 'hello'

        def foo() -> i32:
            a, b, c = make_tuple()
            return a + b
        """)
        x = mod.foo()
        assert x == 3

    def test_unpacking_wrong_number(self):
        mod = self.compile(
        """
        def make_tuple() -> tuple:
            return 1, 2

        def foo() -> void:
            a, b, c = make_tuple()
        """)
        msg = "Wrong number of values to unpack: expected 3, got 2"
        with pytest.raises(SPyError, match=msg):
            mod.foo()

    def test_unpacking_wrong_type(self):
        src = """
        def foo() -> void:
            a, b, c = 42
        """
        errors = expect_errors(
            '`i32` does not support unpacking',
            ('this is `i32`', '42'),
        )
        self.compile_raises(src, 'foo', errors)
