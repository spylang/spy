import pytest
from spy.fqn import FQN
from spy.errors import SPyError
from spy.vm.b import B
from spy.fqn import FQN
from spy.tests.support import (CompilerTest, skip_backends, expect_errors, only_interp, no_C)

class TestMetaFunc(CompilerTest):

    def test_simple(self):
        mod = self.compile("""
        from operator import OpSpec

        @blue.metafunc
        def foo(v_x):
            if v_x.static_type == i32:
               def impl_i32(x: i32) -> i32:
                   return x * 2
               return OpSpec(impl_i32)
            elif v_x.static_type == str:
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
        assert mod.test2() == 'hello world'

    @pytest.mark.skip(reason='implement me')
    def test_wrong_args(self):
        mod = self.compile("""
        from operator import OpSpec

        @blue.metafunc
        def m(v_x):
           def impl_i32(x: i32) -> i32:
               return x * 2
           return OpSpec(impl_i32)

        def foo() -> i32:
            return m()
        """)
        mod.foo()
