# write test for unary neg

from typing import Annotated
import pytest
from spy.vm.primitive import W_I32, W_Dynamic, W_Void
from spy.vm.b import B
from spy.vm.object import Member
from spy.vm.builtin import builtin_func, builtin_type, builtin_method
from spy.vm.w import W_Type, W_Object, W_Str
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.registry import ModuleRegistry
from spy.vm.vm import SPyVM
from spy.tests.support import CompilerTest, no_C, expect_errors

class W_MyClass(W_Object):

    def __init__(self, w_x: W_I32) -> None:
        self.w_x = w_x

    @builtin_method('__new__')
    @staticmethod
    def w_new(vm: 'SPyVM', w_x: W_I32) -> 'W_MyClass':
        return W_MyClass(w_x)

    @builtin_method('__NEG__', color='blue')
    @staticmethod
    def w_NEG(vm: 'SPyVM', wop_self: W_OpArg) -> W_OpImpl:
        @builtin_func('ext')
        def w_neg(vm: 'SPyVM', w_self: W_MyClass) -> W_I32:
            x = vm.unwrap_i32(w_self.w_x)
            return vm.wrap(-x)  # type: ignore
        return W_OpImpl(w_neg)


@no_C
class TestOperatorUnaryOp(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def setup_ext(self) -> None:
        EXT = ModuleRegistry('ext')
        EXT.builtin_type('MyClass')(W_MyClass)
        self.vm.make_module(EXT)

    def test_neg(self):
        self.setup_ext()
        src = """
        from ext import MyClass

        def foo(x: i32) -> i32:
            obj = MyClass(x)
            return -obj
        """
        mod = self.compile(src)
        assert mod.foo(5) == -5
        assert mod.foo(-10) == 10
        assert mod.foo(0) == 0
