import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors


class TestTange(CompilerTest):
    def test_simple(self):
        src = """
        from _tuple import tuple

        def make_tuple(a: str, b: i32, c: i8) -> tuple[str, i32, i8]:
            return (a, b, c)
        """
        mod = self.compile(src)
        t = mod.make_tuple("hello", 42, -5)
        assert t == ("hello", 42, -5)
        assert t[0] == "hello"
        assert t[1] == 42

    def test_getitem(self):
        src = """
        from _tuple import tuple

        def foo(x: i32, y: i32) -> i32:
            t = tuple[int, int](x, y)
            return t[1]
        """
        mod = self.compile(src)
        res = mod.foo(10, 20)
        assert res == 20

    def test_len(self):
        mod = self.compile("""
        from _tuple import tuple

        def foo() -> i32:
            tup = tuple[int, int, str](1, 2, 'hello')
            return len(tup)
        """)
        x = mod.foo()
        assert x == 3

    def test_len_blue(self):
        mod = self.compile("""
        @blue
        def get_tup():
            return (1, "hi")

        @blue
        def assert_blue(x):
            return x

        def foo() -> i32:
            a = get_tup()
            return assert_blue(len(a))
        """)
        x = mod.foo()
        assert x == 2

    def test_repr_str(self):
        mod = self.compile("""
        def repr_empty() -> str:
            return repr(())

        def repr_singleton(item: int) -> str:
            return repr((item,))

        def repr_pair(first: int, second: int) -> str:
            return repr((first, second))

        def repr_heterogeneous(first: str, second: int) -> str:
            return repr((first, second))

        def repr_nested(first: int, second: int, third: int) -> str:
            return repr((first, (second, third)))

        def str_pair(first: int, second: int) -> str:
            return str((first, second))
        """)
        assert mod.repr_empty() == "()"
        assert mod.repr_singleton(1) == "(1,)"
        assert mod.repr_pair(1, 2) == "(1, 2)"
        assert mod.repr_heterogeneous("hello", 42) == "('hello', 42)"
        assert mod.repr_nested(1, 2, 3) == "(1, (2, 3))"
        assert mod.str_pair(1, 2) == "(1, 2)"

    def test_eq(self):
        mod = self.compile("""
        def tup1() -> tuple[int, int]:
            return 1, 2

        def tup2() -> tuple[int, int]:
            return 3, 4

        def foo() -> bool:
            return tup1() == tup1()

        def bar() -> bool:
            return tup1() == tup2()
        """)
        assert mod.foo()
        assert not mod.bar()

    def test_contains(self):
        mod = self.compile("""
        from _tuple import tuple

        def c0(v: int) -> bool:
            t = tuple[()]()
            return v in t

        def c2(v: int) -> bool:
            t = tuple[int, int](1, 2)
            return v in t
        """)
        assert mod.c0(1) == False
        assert mod.c2(1) == True
        assert mod.c2(3) == False

    def test_contains_heterogeneous_error(self):
        src = """
        from _tuple import tuple

        def c() -> bool:
            t = tuple[str, int]("hello", 42)
            return 42 in t
        """
        errors = expect_errors(
            "'in' is not supported on heterogeneous tuples",
        )
        self.compile_raises(src, "c", errors)

    def test_specialized_literal(self):
        src = """
        from _tuple import tuple
        from __spy__ import Specialized, specialize, COLOR

        def getitem_val() -> i32:
            t = specialize(3), 1, "hello"
            return t[0]

        def getitem_color() -> str:
            t = specialize(3), 1, "hello"
            return COLOR(t[0])

        def check_static_types() -> bool:
            t = specialize(3), 1, "hello"
            TUP = tuple[Specialized[3], int, str]
            return STATIC_TYPE(t) == TUP and STATIC_TYPE(t[0]) == i32
        """
        mod = self.compile(src)
        assert mod.getitem_val() == 3
        assert mod.getitem_color() == "blue"
        assert mod.check_static_types()

    def test_specialized_ctor(self):
        src = """
        from _tuple import tuple
        from __spy__ import Specialized, specialize

        TUP = tuple[Specialized[3], str]

        def accepts_i32() -> i32:
            t = TUP(3, "hello")
            return t[0]

        def accepts_specialized() -> i32:
            t = TUP(specialize(3), "hello")
            return t[0]

        def rejects_wrong_i32() -> i32:
            t = TUP(5, "hello")
            return t[0]

        def rejects_wrong_specialized() -> i32:
            t = TUP(specialize(5), "hello")
            return t[0]
        """
        mod = self.compile(src, error_mode="lazy")
        assert mod.accepts_i32() == 3
        assert mod.accepts_specialized() == 3

        msg = "tuple item 0 does not match the specialized value"
        with SPyError.raises("W_TypeError", match=msg):
            mod.rejects_wrong_i32()
        with SPyError.raises("W_TypeError", match=msg):
            mod.rejects_wrong_specialized()
