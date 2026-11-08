import pytest

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

    @no_C
    def test_STATIC_TYPE(self):
        mod = self.compile("""
        def foo() -> type:
            x = 42
            return STATIC_TYPE(x)
        """)
        w_T = mod.foo(unwrap=False)
        assert w_T is B.w_i32

    @no_C
    def test_STATIC_TYPE_side_effects(self):
        if self.backend == "doppler":
            pytest.skip("fixme: side effects of arguments which are redshifted away")

        src = """
        var x: i32 = 0

        def get_x() -> i32:
            return x

        def inc() -> i32:
            global x
            x = x + 1
            return x

        def foo() -> type:
            return STATIC_TYPE(inc())
        """
        mod = self.compile(src)
        assert mod.get_x() == 0
        w_T = mod.foo(unwrap=False)
        assert w_T is B.w_i32
        assert mod.get_x() == 1

    def test_side_effects_of_dropped_MetaArgs(self):
        src = """
        from operator import OpSpec

        var x: i32 = 0

        def get_x() -> i32:
            return x

        def inc() -> i32:
            global x
            x = x + 1
            return x

        @blue.metafunc
        def bar(m_x):
            def impl() -> i32:
                return 42
            return OpSpec(impl, []) # NOTE: here we ignore m_x

        def foo() -> i32:
            return bar(inc())
        """
        mod = self.compile(src)
        assert mod.get_x() == 0
        assert mod.foo() == 42
        assert mod.get_x() == 1

    def test_dropped_MetaArg_evaluation_order(self):
        src = """
        from operator import OpSpec

        var log: i32 = 0

        def get_log() -> i32:
            return log

        def step(k: i32) -> i32:
            global log
            log = log * 10 + k
            return k

        @blue.metafunc
        def bar(m_a, m_b, m_c):
            def impl(a: i32, c: i32) -> i32:
                return a * 10 + c
            return OpSpec(impl, [m_a, m_c]) # NOTE: here we ignore m_b

        def foo() -> i32:
            return bar(step(1), step(2), step(3))
        """
        mod = self.compile(src)
        assert mod.foo() == 13
        assert mod.get_log() == 123

    def test_dropped_trailing_MetaArg_evaluation_order(self):
        src = """
        from operator import OpSpec

        var log: i32 = 0

        def get_log() -> i32:
            return log

        def step(k: i32) -> i32:
            global log
            log = log * 10 + k
            return k

        @blue.metafunc
        def bar(m_a, m_b):
            def impl(a: i32) -> i32:
                return a
            return OpSpec(impl, [m_a]) # NOTE: here we ignore m_b

        def foo() -> i32:
            return bar(step(1), step(2))
        """
        mod = self.compile(src)
        assert mod.foo() == 1
        assert mod.get_log() == 12

    def test_reordered_MetaArgs_evaluation_order(self):
        src = """
        from operator import OpSpec

        var log: i32 = 0

        def get_log() -> i32:
            return log

        def step(k: i32) -> i32:
            global log
            log = log * 10 + k
            return k

        @blue.metafunc
        def bar(m_a, m_b):
            def impl(b: i32, a: i32) -> i32:
                return b * 10 + a
            return OpSpec(impl, [m_b, m_a]) # NOTE: here we swap the args

        def foo() -> i32:
            return bar(step(1), step(2))
        """
        mod = self.compile(src)
        assert mod.foo() == 21
        assert mod.get_log() == 12

    def test_duplicated_MetaArg_evaluated_once(self):
        src = """
        from operator import OpSpec

        var log: i32 = 0

        def get_log() -> i32:
            return log

        def step(k: i32) -> i32:
            global log
            log = log * 10 + k
            return k

        @blue.metafunc
        def bar(m_a):
            def impl(a1: i32, a2: i32) -> i32:
                return a1 * 10 + a2
            return OpSpec(impl, [m_a, m_a]) # NOTE: here we pass m_a twice

        def foo() -> i32:
            return bar(step(1))
        """
        mod = self.compile(src)
        assert mod.foo() == 11
        assert mod.get_log() == 1

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
