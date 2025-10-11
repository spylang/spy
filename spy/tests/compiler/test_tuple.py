import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors, no_C


# Eventually we want to remove the @only_interp, but for now the C backend
# doesn't support lists
@no_C
class TestTuple(CompilerTest):
    def test_literal(self):
        mod = self.compile("""
        def foo() -> dynamic:
            return 1, 2, 'hello'
        """)
        tup = mod.foo()
        assert tup == (1, 2, "hello")

    def test_getitem(self):
        mod = self.compile("""
        def foo(i: i32) -> dynamic:
            tup = 1, 2, 'hello'
            return tup[i]
        """)
        x = mod.foo(0)
        assert x == 1
        y = mod.foo(2)
        assert y == "hello"

    def test_len(self):
        mod = self.compile("""
        def foo() -> i32:
            tup = 1, 2, 'hello'
            return len(tup)
        """)
        x = mod.foo()
        assert x == 3

    def test_unpacking(self):
        mod = self.compile("""
        @blue
        def make_tuple() -> tuple:
            return 1, 2, 'hello'

        def foo() -> i32:
            a, b, c = make_tuple()
            return a + b
        """)
        x = mod.foo()
        assert x == 3

    def test_unpacking_wrong_number(self):
        src = """
        @blue
        def make_tuple() -> tuple:
            return 1, 2

        def foo() -> None:
            a, b, c = make_tuple()
        """
        errors = expect_errors(
            "Wrong number of values to unpack",
            ("expected 3 values", "a, b, c"),
            ("got 2 values", "make_tuple()"),
        )
        self.compile_raises(src, "foo", errors)

    def test_unpacking_wrong_type(self):
        src = """
        def foo() -> None:
            a, b, c = 42
        """
        errors = expect_errors(
            "`i32` does not support unpacking",
            ("this is `i32`", "42"),
        )
        self.compile_raises(src, "foo", errors)

    @pytest.mark.skip("implement me")
    def test_unpacking_wrong_color(self):
        # this is temporary: for now you can only unpack blue
        # tuples. Eventually we want to be able to unpack red tuple with known
        # arity.
        sec = """
        def make_tuple() -> tuple:
            return 1, 2, 'hello'

        def foo() -> i32:
            a, b, c = make_tuple()
            return a + b
        """
        assert False, "fixme"
        errors = "WRITE ME"
        self.compile_raises(src, "foo", errors)

    def test_eq(self):
        mod = self.compile("""
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
