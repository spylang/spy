import pytest
from spy.tests.support import CompilerTest, expect_errors, only_interp

class TestImporting(CompilerTest):

    def test_import(self):
        mod = self.compile("""
        from builtins import abs as my_abs

        def foo(x: i32) -> i32:
            return my_abs(x)
        """)
        #
        assert mod.foo(-20) == 20

    def test_import_errors_1(self):
        ctx = expect_errors(
            "cannot import `builtins.aaa`",
            ("attribute `aaa` does not exist in module `builtins`", "aaa")
        )
        with ctx:
            self.compile("""
            from builtins import aaa
            """)

    def test_import_errors_2(self):
        ctx = expect_errors(
            "cannot import `xxx.aaa`",
            ("module `xxx` does not exist", "from xxx import aaa"),
        )
        with ctx:
            self.compile("""
            from xxx import aaa
            """)

    def test_function_in_other_module(self):
        self.SKIP_SPY_BACKEND_SANITY_CHECK = True
        self.write_file("delta.spy", """
        def get_delta() -> i32:
            return 10
        """)

        mod = self.compile("""
        from delta import get_delta
        def inc(x: i32) -> i32:
            return x + get_delta()
        """)

        assert mod.inc(4) == 14

    def test_type_in_other_module(self):
        self.SKIP_SPY_BACKEND_SANITY_CHECK = True
        self.write_file("point.spy", """
        @struct
        class Point:
            x: i32
            y: i32
        """)

        mod = self.compile("""
        from unsafe import gc_alloc, ptr
        from point import Point

        def make_point(x: i32, y: i32) -> ptr[Point]:
            p = gc_alloc(Point)(1)
            p.x = x
            p.y = y
            return p

        def foo(x: i32, y: i32) -> f64:
            p = make_point(x, y)
            return p.x + p.y
        """)

        assert mod.foo(3, 4) == 7

    @only_interp
    def test_nested_imports(self, capsys):
        self.SKIP_SPY_BACKEND_SANITY_CHECK = True
        self.write_file("aaa.spy", """
        import a1
        import a2

        @blue
        def __INIT__(mod):
            print('aaa')
        """)
        self.write_file("bbb.spy", """
        import aaa
        import b1
        import b2

        @blue
        def __INIT__(mod):
            print('bbb')
        """)
        self.write_file("a1.spy", """
        @blue
        def __INIT__(mod):
            print('a1')
        """)
        self.write_file("a2.spy", """
        @blue
        def __INIT__(mod):
            print('a2')
        """)
        self.write_file("b1.spy", """
        @blue
        def __INIT__(mod):
            print('b1')
        """)
        self.write_file("b2.spy", """
        @blue
        def __INIT__(mod):
            print('b2')
        """)
        mod = self.compile("""
        import aaa
        import bbb

        @blue
        def __INIT__(mod):
            print('main')
        """)
        out, err = capsys.readouterr()
<<<<<<< HEAD
        mods = out.strip().split('\n')
        assert mods == ['a1', 'a2', 'aaa', 'b1', 'b2', 'bbb', 'main']

    def test_circular_type_refs(self):
        self.SKIP_SPY_BACKEND_SANITY_CHECK = True
        self.write_file("vec.spy", """
        @blue.generic
        def Vec2(T):
            @struct
            class _Vec2:
                a: T
                b: T
            return _Vec2
        """)
        src = """
        from vec import Vec2

        @struct
        class Point:
            x: int
            y: int

        def foo() -> Point:
            v = Vec2[Point](Point(1, 1), Point(2, 2))
            return v.a
        """
        mod = self.compile(src)
        assert mod.foo() == (1, 1)
=======
        mods = out.strip().split("\n")
        assert mods == ["a1", "a2", "aaa", "b1", "b2", "bbb", "main"]
>>>>>>> 0c57b4ea (ruff: replace single quote with doublequotes)
