from spy.tests.support import CompilerTest, expect_errors, only_interp


class TestImporting(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def test_import(self):
        mod = self.compile("""
        from builtins import abs as my_abs

        def foo(x: i32) -> i32:
            return my_abs(x)
        """)
        assert mod.foo(-20) == 20

    def test_import_errors_1(self):
        ctx = expect_errors(
            "cannot import `builtins.aaa`",
            ("attribute `aaa` does not exist in module `builtins`", "aaa"),
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

    def test_import_wrong_py_module(self):
        self.write_file("mymodule.py", "x = 42")
        ctx = expect_errors(
            "cannot import `mymodule.x`",
            (
                "file `mymodule.py` exists, but py files cannot be imported",
                "from mymodule import x",
            ),
        )
        with ctx:
            self.compile("""
            from mymodule import x
            """)

    def test_function_in_other_module(self):
        src = """
        def get_delta() -> i32:
            return 10
        """
        self.write_file("delta.spy", src)

        mod = self.compile("""
        from delta import get_delta
        def inc(x: i32) -> i32:
            return x + get_delta()
        """)

        assert mod.inc(4) == 14

    def test_type_in_other_module(self):
        src = """
        @struct
        class Point:
            x: i32
            y: i32
        """
        self.write_file("point.spy", src)

        mod = self.compile("""
        from unsafe import raw_alloc, raw_ptr
        from point import Point

        def make_point(x: i32, y: i32) -> raw_ptr[Point]:
            p = raw_alloc[Point](1)
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
        src = """
        import a1
        import a2

        @blue
        def __INIT__(mod):
            print('aaa')
        """
        self.write_file("aaa.spy", src)
        src = """
        import aaa
        import b1
        import b2

        @blue
        def __INIT__(mod):
            print('bbb')
        """
        self.write_file("bbb.spy", src)
        src = """
        @blue
        def __INIT__(mod):
            print('a1')
        """
        self.write_file("a1.spy", src)
        src = """
        @blue
        def __INIT__(mod):
            print('a2')
        """
        self.write_file("a2.spy", src)
        src = """
        @blue
        def __INIT__(mod):
            print('b1')
        """
        self.write_file("b1.spy", src)
        src = """
        @blue
        def __INIT__(mod):
            print('b2')
        """
        self.write_file("b2.spy", src)
        self.compile("""
        import aaa
        import bbb

        @blue
        def __INIT__(mod):
            print('main')
        """)
        out, _ = capsys.readouterr()
        mods = out.strip().split("\n")
        assert mods == ["a1", "a2", "aaa", "b1", "b2", "bbb", "main"]

    def test_circular_type_refs(self):
        src = """
        @blue.generic
        def Vec2(T):
            @struct
            class _Vec2:
                a: T
                b: T
            return _Vec2
        """
        self.write_file("vec.spy", src)
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

    def test_multi_step_import(self):
        self.write_file("a.spy", "X = 42")
        self.write_file("b.spy", "from a import X")
        src = """
        from b import X

        def foo() -> i32:
            return X
        """
        mod = self.compile(src)
        assert mod.foo() == 42

    def test_multiple_mains(self, capfd):
        src = """
        def foo() -> i32:
            return 42

        def main() -> None:
            print("this should never be executed")
        """
        self.write_file("a.spy", src)

        src = """
        from a import foo
        def main() -> None:
            print(foo())
        """
        mod = self.compile(src)
        mod.main()
        if self.backend == "C":
            mod.ll.call("spy_flush")
        out, err = capfd.readouterr()
        assert out == "42\n"

    def test_implicit_imports(self):
        mod = self.compile("""
        def foo() -> i32:
            result: i32 = 0
            for x in range(3):
                result = result + x
            return result
        """)
        assert mod.foo() == 3  # 0 + 1 + 2
