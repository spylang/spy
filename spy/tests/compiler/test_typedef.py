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

    def test_getattr(self):
        mod = self.compile("""
        from types import makeTypeDef

        # XXX temporary workaround: currently there is a bug and we don't
        # assign a FQN to getattr_double if it's defined inside makeMyInt, we
        # should move it inside when the bug is fixed
        def getattr_double(self: i32, attr: str) -> i32:
            i: i32 = self
            return i * 2

        @blue
        def makeMyInt():
            MyInt = makeTypeDef('MyInt', i32)

            ## def getattr_double(self: MyInt, attr: str) -> i32:
            ##     i: i32 = self
            ##     return i * 2

            @blue
            def __getattr__(self, attr):
                if attr == "double":
                    return getattr_double
                return NotImplemented

            MyInt.__getattr__ = __getattr__
            return MyInt

        MyInt = makeMyInt()

        def foo(x: i32) -> i32:
            y: MyInt = x
            return y.double
        """)
        assert mod.foo(10) == 20
