import pytest

from spy.errors import SPyError
from spy.fqn import FQN
from spy.tests.support import (
    CompilerTest,
    expect_errors,
    no_C,
    only_interp,
    skip_backends,
)
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
