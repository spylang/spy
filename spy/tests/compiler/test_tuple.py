import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors, only_interp
from spy.vm.b import B
from spy.vm.modules.__spy__.interp_tuple import W_InterpTuple


class TestTuple(CompilerTest):
    """
    These are only few of the tests about tuples, mostly to check that:

      1. tuple[T1, T2, ...] does the right thing

      2. the tuple literal syntax "(a, b, c)" works

    The actual behavior of tuple objects is tested by stdlib/test__tuple.py and
    test_interp_tuple.py
    """

    def test_literal_stdlib(self):
        mod = self.compile("""
        def foo() -> tuple[i32, i32]:
            return 1, 2
        """)
        tup = mod.foo()
        assert tup == (1, 2)

    @only_interp
    def test_literal_interp_tuple(self):
        mod = self.compile("""
        def foo() -> tuple[int, type]:
            return 1, int
        """)
        w_tup = mod.foo(unwrap=False)
        assert isinstance(w_tup, W_InterpTuple)
        w_x, w_T = w_tup.items_w
        assert self.vm.unwrap_i32(w_x) == 1
        assert w_T is B.w_i32

    def test_variadic_starred(self):
        src = """
        from operator import OpSpec, MetaArg

        @blue.metafunc
        def foo(*m_args):
            m_x: MetaArg = m_args[0]
            m_y: MetaArg = m_args[1]
            names = (*m_args,)
            assert names[0] is m_x
            assert names[1] is m_y

            T = m_x.static_type
            assert m_y.static_type == T

            def impl_str(x: T, y: T) -> T:
                return x + y

            return OpSpec(impl_str, [*m_args])

        def test_i32(x: i32, y: i32) -> i32:
            return foo(x, y)

        def test_str(x: str, y: str) -> str:
            return foo(x, y)
        """
        mod = self.compile(src)
        assert mod.test_i32(1, 2) == 3
        assert mod.test_str("S", "Py") == "SPy"

    def test_unpacking_blue(self):
        mod = self.compile("""
        @blue
        def make_tuple():
            return 1, 2, 'hello'

        def foo() -> i32:
            a, b, c = make_tuple()
            return a + b
        """)
        x = mod.foo()
        assert x == 3

    def test_unpacking_red(self):
        mod = self.compile("""
        def make_tuple() -> tuple[i32, i32, str]:
            return 1, 2, 'hello'

        def foo() -> i32:
            a, b, c = make_tuple()
            return a + b
        """)
        x = mod.foo()
        assert x == 3

    def test_literal_red_args(self):
        mod = self.compile("""
        def foo(a: i32, b: i32) -> tuple[i32, i32]:
            return a, b
        """)
        tup = mod.foo(3, 4)
        assert tup == (3, 4)

    def test_return_tuple(self):
        src = """
        def foo() -> tuple[i32, i32, i32]:
            return 1, 2, 3

        def nested() -> tuple[i32, tuple[i32, i32]]:
            return 1, (2, 3)

        def mixed_type() -> tuple[i32, f64, bool, str]:
            return 1, 2.5, True, "hello"
        """
        mod = self.compile(src)
        tup = mod.foo()
        assert tup == (1, 2, 3)

        tup = mod.nested()
        assert tup == (1, (2, 3))

        tup = mod.mixed_type()
        assert tup == (1, 2.5, True, "hello")

    def test_unpacking_wrong_number(self):
        src = """
        def make_tuple() -> tuple[int, int]:
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

    def test_prebuilt_constant(self):
        src = """
        @blue
        def get_tup():
            return (1, 2, "hello")

        def foo() -> str:
            t = get_tup()
            return t[2]
        """
        mod = self.compile(src)
        assert mod.foo() == "hello"
