from spy.tests.support import CompilerTest, expect_errors, no_C
from spy.vm.b import B


class TestMetaFunc(CompilerTest):
    def test_simple(self):
        mod = self.compile("""
        from operator import OpSpec

        @blue.metafunc
        def foo(m_x):
            if m_x.static_type == i32:
               def impl_i32(x: i32) -> i32:
                   return x * 2
               return OpSpec(impl_i32)
            elif m_x.static_type == str:
               def impl_str(x: str) -> str:
                   return x + ' world'
               return OpSpec(impl_str)
            raise StaticError("unsupported type")

        def test1() -> i32:
            return foo(5)

        def test2() -> str:
            return foo('hello')
        """)
        assert mod.test1() == 10
        assert mod.test2() == "hello world"

    def test_call_via_module_attr(self):
        src = """
        from operator import OpSpec

        @blue.metafunc
        def foo(m_x):
            if m_x.static_type == i32:
                def impl_i32(x: i32) -> i32:
                    return x * 2
                return OpSpec(impl_i32)
            elif m_x.static_type == str:
                def impl_str(x: str) -> str:
                    return x + ' world'
                return OpSpec(impl_str)
            raise StaticError("unsupported type")
        """
        self.write_file("mymod.spy", src)

        mod = self.compile("""
        import mymod

        def test1() -> i32:
            return mymod.foo(5)

        def test2() -> str:
            return mymod.foo('hello')
        """)
        assert mod.test1() == 10
        assert mod.test2() == "hello world"

    def test_method(self):
        mod = self.compile("""
        from operator import OpSpec

        @struct
        class Foo:
            a: int

            @blue.metafunc
            def foo(m_self, m_x):
                def impl(self: Foo, x: i32) -> i32:
                    return x * self.a
                return OpSpec(impl)

        def test1() -> i32:
            return Foo(2).foo(5)
        """)
        assert mod.test1() == 10

    def test_wrong_argcount(self):
        src = """
        @blue.metafunc
        def m(m_x):
            pass

        def foo() -> i32:
            return m()
        """
        errors = expect_errors(
            "this function takes 1 argument but 0 arguments were supplied",
            ("function defined here", "def m(m_x):"),
        )
        self.compile_raises(src, "foo", errors)

    def test_wrong_restype(self):
        src = """
        @blue.metafunc
        def m():
            # the metacall protocol expects an OpSpec, not an int
            return 42

        def foo() -> i32:
            return m()
        """
        errors = expect_errors(
            "wrong metafunc return type: expected `operator::OpSpec`, got `i32`",
            ("this is a metafunc", "m"),
            ("metafunc defined here", "def m():"),
        )
        self.compile_raises(src, "foo", errors)

    def test_null_opspec(self):
        src = """
        from operator import OpSpec

        @blue.metafunc
        def m(m_x, m_y):
            return OpSpec.NULL

        def foo() -> i32:
            return m(1, 'hello')
        """
        errors = expect_errors(
            "`m` does not support arguments of type `i32`, `str`",
            ("this is `i32`", "1"),
            ("this is `str`", "'hello'"),
            ("metafunc defined here", "def m(m_x, m_y):"),
        )
        self.compile_raises(src, "foo", errors)

    @no_C
    def test_STATIC_TYPE(self):
        mod = self.compile("""
        def foo() -> type:
            x = 42
            return STATIC_TYPE(x)
        """)
        w_T = mod.foo(unwrap=False)
        assert w_T is B.w_i32

    def test_loc_source(self):
        src = """
        from operator import OpSpec

        @blue.metafunc
        def meta(m_x):
            filename = m_x.loc.filename
            source = m_x.loc.get_src()
            def impl(x: i32) -> tuple[str, str]:
                return source, filename
            return OpSpec(impl)

        def foo() -> tuple[str, str]:
            var x = 2
            return meta(x + 2)
        """
        mod = self.compile(src)
        result = mod.foo()
        assert result[0] == "x + 2"
        assert result[1].endswith("test.spy")

    @no_C
    def test_loc_args_m(self):
        src = """
        from operator import OpSpec

        @blue.metafunc
        def meta(*args_m):
            filename = args_m.loc.filename
            def impl() -> str:
                return filename
            return OpSpec(impl)

        def foo() -> str:
            return meta()
        """
        mod = self.compile(src)
        filename = mod.foo()
        assert filename.endswith("test.spy")

    @no_C
    def test_args_m_types(self):
        src = """
        from operator import OpSpec

        @struct
        class Point:
            x: i32
            y: i32

        @blue.metafunc
        def meta(*args_m):
            for i in range(len(args_m)):
                assert args_m.types[i] == args_m[i].static_type
            return OpSpec.const("ok")

        def foo() -> str:
            return meta(1, "a", Point(1, 2))
        """
        mod = self.compile(src)
        assert mod.foo() == "ok"

    @no_C
    def test_args_m_static_type(self):
        src = """
        from operator import OpSpec, MetaArg

        @blue.metafunc
        def meta(*args_m):
            assert STATIC_TYPE(args_m[0]) == MetaArg
            m_x, m_y = args_m
            assert STATIC_TYPE(m_x) == MetaArg
            assert STATIC_TYPE(m_y) == MetaArg

            def impl(x: i32, y: i32) -> i32:
                return x + y

            return OpSpec(impl, [m_x, m_y])

        def foo(a: i32, b: i32) -> i32:
            return meta(a, b)
        """
        mod = self.compile(src)
        assert mod.foo(3, 4) == 7

    @no_C
    def test_args_m_iter(self):
        src = """
        from operator import OpSpec, MetaArg

        @blue.metafunc
        def meta(*args_m):
            n = 0
            for m in args_m:
                assert STATIC_TYPE(m) == MetaArg
                assert m.static_type == i32
                n = n + 1
            return OpSpec.const(n)

        def foo() -> i32:
            return meta(1, 2, 3)
        """
        mod = self.compile(src)
        assert mod.foo() == 3

    @no_C
    def test_args_m_len_is_blue(self):
        src = """
        from operator import OpSpec
        from __spy__ import COLOR

        @blue.metafunc
        def meta(*args_m):
            N = len(args_m)
            assert N == 2
            assert COLOR(N) == "blue"
            return OpSpec.const(3)

        def foo() -> i32:
            var a = 1
            var b = 2.0
            return meta(a, b)
        """
        mod = self.compile(src)
        assert mod.foo() == 3
