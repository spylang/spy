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

# EXT::MyClass, which is used in all the tests
class W_MyClass(W_Object):

    def __init__(self, w_x: W_I32) -> None:
        self.w_x = w_x

    @builtin_method('__new__')
    @staticmethod
    def w_spy_new(vm: 'SPyVM', w_x: W_I32) -> 'W_MyClass':
        return W_MyClass(w_x)

    @builtin_method('__getitem__')
    @staticmethod
    def w_getitem(vm: 'SPyVM', w_obj: 'W_MyClass', w_i: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_obj.w_x)
        i = vm.unwrap_i32(w_i)
        return vm.wrap(x + i)


@no_C
class TestOperatorSimple(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def test_getitem(self):
        EXT = ModuleRegistry('ext')
        EXT.builtin_type('MyClass')(W_MyClass)
        self.vm.make_module(EXT)
        src = """
        from ext import MyClass

        def foo(x: i32) -> i32:
            obj = MyClass(x)
            return obj[5]
        """
        mod = self.compile(src)
        assert mod.foo(4) == 9
