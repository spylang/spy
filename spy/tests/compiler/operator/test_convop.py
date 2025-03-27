from typing import Annotated
import pytest
from spy.vm.primitive import W_I32, W_F64, W_Dynamic, W_Bool, W_Void
from spy.vm.b import B
from spy.vm.object import Member
from spy.vm.builtin import builtin_func, builtin_type, builtin_method
from spy.vm.w import W_Type, W_Object, W_Str
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.registry import ModuleRegistry
from spy.vm.vm import SPyVM
from spy.tests.support import CompilerTest, no_C, expect_errors


class W_MyClass(W_Object):
    w_x: Annotated[W_I32, Member('x')]

    def __init__(self, w_x: W_I32) -> None:
        self.w_x = w_x

    @builtin_method('__new__')
    @staticmethod
    def w_new(vm: 'SPyVM', w_x: W_I32) -> 'W_MyClass':
        return W_MyClass(w_x)

    @builtin_method('__CONVERT_TO__', color='blue')
    @staticmethod
    def w_CONVERT_TO(vm: 'SPyVM', w_target_type: W_Type,
                     wop_self: W_OpArg) -> W_OpImpl:

        @builtin_func('ext')
        def w_to_i32(vm: 'SPyVM', w_self: W_MyClass) -> W_I32:
            return w_self.w_x

        @builtin_func('ext')
        def w_to_str(vm: 'SPyVM', w_self: W_MyClass) -> W_Str:
            x = vm.unwrap_i32(w_self.w_x)
            return vm.wrap(str(x))  # type: ignore

        if w_target_type is B.w_i32:
            vm.add_global(w_to_i32.fqn, w_to_i32)
            return W_OpImpl(w_to_i32)
        elif w_target_type is B.w_str:
            vm.add_global(w_to_str.fqn, w_to_str)
            return W_OpImpl(w_to_str)
        return W_OpImpl.NULL

    @builtin_method('__CONVERT_FROM__', color='blue')
    @staticmethod
    def w_CONVERT_FROM(vm: 'SPyVM', w_source_type: W_Type,
                       wop_val: W_OpArg) -> W_OpImpl:
        @builtin_func('ext')
        def w_from_str(vm: 'SPyVM', w_val: W_Str) -> W_MyClass:
            s = vm.unwrap_str(w_val)
            w_x = vm.wrap(int(s))
            return W_MyClass(w_x)  # type: ignore

        if w_source_type is B.w_str:
            vm.add_global(w_from_str.fqn, w_from_str)
            return W_OpImpl(w_from_str)
        return W_OpImpl.NULL


@no_C
class TestConvop(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def setup_ext(self) -> None:
        EXT = ModuleRegistry('ext')
        EXT.builtin_type('MyClass')(W_MyClass)
        self.vm.make_module(EXT)

    def test_convert_to(self):
        self.setup_ext()
        src = """
        from ext import MyClass

        def convert_to_i32(x: i32) -> i32:
            obj = MyClass(x)
            return obj

        def convert_to_str(x: i32) -> str:
            obj = MyClass(x)
            return obj
        """
        mod = self.compile(src)
        assert mod.convert_to_i32(42) == 42
        assert mod.convert_to_str(42) == '42'

    def test_convert_from(self):
        self.setup_ext()
        src = """
        from ext import MyClass

        def convert_from_str() -> MyClass:
            return "42"
        """
        mod = self.compile(src)
        w_result = mod.convert_from_str(unwrap=False)
        assert isinstance(w_result, W_MyClass)
        assert self.vm.unwrap_i32(w_result.w_x) == 42
