import re
import pytest
from spy.errors import SPyTypeError
from spy.fqn import FQN
from spy.vm.b import B
from spy.vm.function import W_ASTFunc
from spy.vm.modules.types import W_TypeDef
from spy.tests.support import (CompilerTest, skip_backends,  expect_errors,
                               only_interp)

class TestTypeDef(CompilerTest):

    def test_cast_from_and_to(self):
        # XXX: for now we allow implicit coversion between a TypeDef and it's
        # origin type because it's simpler, but eventually we want a more
        # explicit way, e.g. TypeDef.cast or something like that.
        mod = self.compile("""
        from types import makeTypeDef
        MyInt = makeTypeDef('MyInt', i32)

        def foo() -> MyInt:
            x: MyInt = 42 # i32 -> MyInt
            return x

        def bar() -> i32:
            x: MyInt = 43 # i32 -> MyInt
            return x      # MyInt -> i32
        """)
        assert mod.foo() == 42
        assert mod.bar() == 43

    @only_interp
    def test_metaclass_setattr(self):
        """
        Test that we can succesfully set attributes on the typedef itself
        """
        mod = self.compile("""
        from types import makeTypeDef

        @blue
        def makeMyInt():
            MyInt = makeTypeDef('MyInt', i32)

            @blue
            def __getattr__(attr):
                return NotImplemented

            MyInt.__getattr__ = __getattr__
            return MyInt
        """)

        w_makeMyInt = mod.makeMyInt.w_func
        w_MyInt = self.vm.call_function(w_makeMyInt, [])
        assert isinstance(w_MyInt, W_TypeDef)
        w_getattr = w_MyInt.w_getattr
        assert isinstance(w_getattr, W_ASTFunc)
        assert w_getattr.fqn == FQN("test::__getattr__#0")
        w_res = self.vm.call_function(w_getattr, [B.w_None])
        assert w_res is B.w_NotImplemented
