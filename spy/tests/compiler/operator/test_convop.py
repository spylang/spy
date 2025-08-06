from typing import Annotated
from spy.vm.primitive import W_I32
from spy.vm.b import B
from spy.vm.member import Member
from spy.vm.builtin import builtin_func, builtin_method
from spy.vm.w import W_Type, W_Object, W_Str
from spy.vm.opspec import W_OpSpec, W_OpArg
from spy.vm.registry import ModuleRegistry
from spy.vm.vm import SPyVM
from spy.tests.support import CompilerTest, no_C


class W_MyClass(W_Object):
    w_x: Annotated[W_I32, Member('x')]

    def __init__(self, w_x: W_I32) -> None:
        self.w_x = w_x

    @builtin_method('__new__')
    @staticmethod
    def w_new(vm: 'SPyVM', w_x: W_I32) -> 'W_MyClass':
        return W_MyClass(w_x)

    @builtin_method('__convert_to__', color='blue', kind='metafunc')
    @staticmethod
    def w_CONVERT_TO(
            vm: 'SPyVM',
            wop_target_type: W_OpArg,
            wop_self: W_OpArg
    ) -> W_OpSpec:
        w_target_type = wop_target_type.w_blueval

        @builtin_func('ext')
        def w_to_i32(vm: 'SPyVM', w_self: W_MyClass) -> W_I32:
            return w_self.w_x

        @builtin_func('ext')
        def w_to_str(vm: 'SPyVM', w_self: W_MyClass) -> W_Str:
            x = vm.unwrap_i32(w_self.w_x)
            return vm.wrap(str(x))

        if w_target_type is B.w_i32:
            vm.add_global(w_to_i32.fqn, w_to_i32)
            return W_OpSpec(w_to_i32)
        elif w_target_type is B.w_str:
            vm.add_global(w_to_str.fqn, w_to_str)
            return W_OpSpec(w_to_str)
        return W_OpSpec.NULL

    @builtin_method('__convert_from__', color='blue', kind='metafunc')
    @staticmethod
    def w_CONVERT_FROM(
            vm: 'SPyVM',
            wop_source_type: W_OpArg,
            wop_val: W_OpArg
    ) -> W_OpSpec:
        w_source_type = wop_source_type.w_blueval

        @builtin_func('ext')
        def w_from_str(vm: 'SPyVM', w_val: W_Str) -> W_MyClass:
            s = vm.unwrap_str(w_val)
            w_x = vm.wrap(int(s))
            return W_MyClass(w_x)

        if w_source_type is B.w_str:
            vm.add_global(w_from_str.fqn, w_from_str)
            return W_OpSpec(w_from_str)
        return W_OpSpec.NULL


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
