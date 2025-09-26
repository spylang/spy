from spy.errors import SPyError
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

    def test_len(self):
        mod = self.compile(
        """
        def foo() -> i32:
            tup = 1, 2, 'hello'
            return len(tup)
        """)
        x = mod.foo()
        assert x == 3

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

        def foo() -> None:
            a, b, c = make_tuple()
        """)
        msg = "Wrong number of values to unpack: expected 3, got 2"
        with SPyError.raises('W_ValueError', match=msg):
            mod.foo()

    def test_unpacking_wrong_type(self):
        src = """
        def foo() -> None:
            a, b, c = 42
        """
        errors = expect_errors(
            '`i32` does not support unpacking',
            ('this is `i32`', '42'),
        )
        self.compile_raises(src, 'foo', errors)

    def test_eq(self):
        mod = self.compile(
        """
        def tup1() -> tuple:
            return 1, 2

        def tup2() -> tuple:
            return 3, 4

        def foo() -> bool:
            return tup1() == tup1()

        def bar() -> bool:
            return tup1() == tup2()
        """)
        assert mod.foo()
        assert not mod.bar()

    def test_blue_tuple(self):
        mod = self.compile(
        """
        @blue
        def make_pair():
            return 1, 2

        def foo() -> i32:
            a, b = make_pair()
            return a + b
        """)
        x = mod.foo()
        assert x == 3
