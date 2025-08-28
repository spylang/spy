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

    def test_wrong_argcount(self):
        src = """
        @blue.metafunc
        def m(v_x):
            pass

        def foo() -> i32:
            return m()
        """
        errors = expect_errors(
            'this function takes 1 argument but 0 arguments were supplied',
            ('function defined here', 'def m(v_x):'),
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
            'wrong metafunc return type: expected `operator::OpSpec`, got `i32`',
            ('this is a metafunc', 'm'),
            ('metafunc defined here', 'def m():'),
        )
        self.compile_raises(src, "foo", errors)
