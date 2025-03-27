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
    def __init__(self, w_base: W_I32) -> None:
        self.w_base = w_base
        self.w_values: dict[W_I32, W_I32] = {}

    @builtin_method('__new__')
    @staticmethod
    def w_new(vm: 'SPyVM', w_base: W_I32) -> 'W_MyClass':
        return W_MyClass(w_base)

    @builtin_method('__GETITEM__', color='blue')
    @staticmethod
    def w_GETITEM(vm: 'SPyVM', wop_self: W_OpArg, wop_i: W_OpArg) -> W_OpImpl:

        @builtin_func('ext')
        def w_getitem(vm: 'SPyVM', w_self: W_MyClass, w_i: W_I32) -> W_I32:
            base = vm.unwrap_i32(w_self.w_base)
            idx = vm.unwrap_i32(w_i)

            # If index exists in dictionary, return that value
            if idx in w_self.w_values:
                return w_self.w_values[idx]

            # Otherwise calculate a value based on base and index
            return vm.wrap(base + idx)  # type: ignore

        return W_OpImpl(w_getitem)

    @builtin_method('__SETITEM__', color='blue')
    @staticmethod
    def w_SETITEM(vm: 'SPyVM', wop_self: W_OpArg, wop_i: W_OpArg,
                  wop_v: W_OpArg) -> W_OpImpl:

        @builtin_func('ext')
        def w_setitem(vm: 'SPyVM', w_self: W_MyClass, w_i: W_I32,
                      w_v: W_I32) -> None:
            idx = vm.unwrap_i32(w_i)
            w_self.w_values[idx] = w_v

        return W_OpImpl(w_setitem)



@no_C
class TestItemop(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def setup_ext(self) -> None:
        EXT = ModuleRegistry('ext')
        EXT.builtin_type('MyClass')(W_MyClass)
        self.vm.make_module(EXT)

    def test_getitem(self):
        self.setup_ext()
        src = """
        from ext import MyClass

        def foo(base: i32, index: i32) -> i32:
            obj = MyClass(base)
            return obj[index]
        """
        mod = self.compile(src)
        assert mod.foo(10, 5) == 15  # 10 + 5 = 15
        assert mod.foo(20, 7) == 27  # 20 + 7 = 27

    def test_setitem(self):
        self.setup_ext()
        src = """
        from ext import MyClass

        def foo(base: i32, index: i32, value: i32) -> i32:
            obj = MyClass(base)
            obj[index] = value
            return obj[index]
        """
        mod = self.compile(src)
        assert mod.foo(10, 5, 42) == 42  # Setting and getting index 5
        assert mod.foo(20, 7, 100) == 100  # Setting and getting index 7
