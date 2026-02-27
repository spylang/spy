import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, expect_errors, no_C


@no_C
class TestInterpTuple(CompilerTest):
    def test_new(self):
        mod = self.compile("""
        from __spy__ import interp_tuple

        def foo() -> interp_tuple:
            return interp_tuple(1, 2, 'hello')
        """)
        tup = mod.foo()
        assert tup == (1, 2, "hello")

    def test_getitem(self):
        mod = self.compile("""
        from __spy__ import interp_tuple

        def foo(i: i32) -> dynamic:
            tup = interp_tuple(1, 2, 'hello')
            return tup[i]
        """)
        x = mod.foo(0)
        assert x == 1
        y = mod.foo(2)
        assert y == "hello"

    def test_len(self):
        mod = self.compile("""
        from __spy__ import interp_tuple

        def foo() -> i32:
            tup = interp_tuple(1, 2, 'hello')
            return len(tup)
        """)
        x = mod.foo()
        assert x == 3

    def test_unpacking(self):
        mod = self.compile("""
        from __spy__ import interp_tuple

        @blue
        def make_tuple() -> interp_tuple:
            return interp_tuple(1, 2, 'hello')

        def foo() -> i32:
            a, b, c = make_tuple()
            return a + b
        """)
        x = mod.foo()
        assert x == 3

    def test_unpacking_wrong_number(self):
        src = """
        from __spy__ import interp_tuple

        @blue
        def make_tuple() -> interp_tuple:
            return interp_tuple(1, 2)

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

    def test_fastiter(self):
        if self.backend != "interp":
            pytest.skip(
                "interp_tuple __fastiter__ is only supported on the interp backend"
            )
        mod = self.compile("""
        from __spy__ import interp_tuple

        @blue
        def make_tuple() -> interp_tuple:
            return interp_tuple(1, 2, 3)

        def foo() -> i32:
            count: i32 = 0
            for item in make_tuple():
                count = count + 1
            return count
        """)
        assert mod.foo() == 3

    def test_eq(self):
        mod = self.compile("""
        from __spy__ import interp_tuple

        def tup1() -> interp_tuple:
            return interp_tuple(1, 2)

        def tup2() -> interp_tuple:
            return interp_tuple(3, 4)

        def foo() -> bool:
            return tup1() == tup1()

        def bar() -> bool:
            return tup1() == tup2()
        """)
        assert mod.foo()
        assert not mod.bar()
