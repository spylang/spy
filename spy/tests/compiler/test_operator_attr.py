from typing import Annotated
import pytest
from spy.vm.primitive import W_I32, W_Dynamic, W_Void
from spy.vm.b import B
from spy.vm.object import Member
from spy.vm.builtin import builtin_func, builtin_type
from spy.vm.w import W_Type, W_Object, W_Str
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.registry import ModuleRegistry
from spy.vm.vm import SPyVM
from spy.tests.support import CompilerTest, no_C

@no_C
class TestAttrOp(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def test_member(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext')

        @EXT.builtin_type('MyClass')
        class W_MyClass(W_Object):
            w_x: Annotated[W_I32, Member('x')]

            def __init__(self) -> None:
                self.w_x = W_I32(0)

            @staticmethod
            def w_spy_new(vm: 'SPyVM', w_cls: W_Type) -> 'W_MyClass':
                return W_MyClass()
        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import MyClass

        @blue
        def foo():
            obj =  MyClass()
            obj.x = 123
            return obj.x
        """)
        x = mod.foo()
        assert x == 123


    def test_getattr_setattr_custom(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext')

        @EXT.builtin_type('MyClass')
        class W_MyClass(W_Object):

            def __init__(self) -> None:
                self.x = 0

            @staticmethod
            def w_spy_new(vm: 'SPyVM', w_cls: W_Type) -> 'W_MyClass':
                return W_MyClass()

            @staticmethod
            def op_GETATTR(vm: 'SPyVM', wop_obj: W_OpArg,
                           wop_attr: W_OpArg) -> W_OpImpl:
                attr = wop_attr.blue_unwrap_str(vm)
                if attr == 'x':
                    @builtin_func('ext', 'getx')
                    def w_fn(vm: 'SPyVM', w_obj: W_MyClass,
                           w_attr: W_Str) -> W_I32:
                        return vm.wrap(w_obj.x)  # type: ignore
                else:
                    @builtin_func('ext', 'getany')
                    def w_fn(vm: 'SPyVM', w_obj: W_MyClass,
                                      w_attr: W_Str) -> W_Str:
                        attr = vm.unwrap_str(w_attr)
                        return vm.wrap(attr.upper() + '--42')  # type: ignore
                return W_OpImpl(w_fn)

            @staticmethod
            def op_SETATTR(vm: 'SPyVM', wop_obj: W_OpArg, wop_attr: W_OpArg,
                           wop_v: W_OpArg) -> W_OpImpl:
                attr = wop_attr.blue_unwrap_str(vm)
                if attr == 'x':
                    @builtin_func('ext')
                    def w_setx(vm: 'SPyVM', w_obj: W_MyClass,
                               w_attr: W_Str, w_val: W_I32) -> W_Void:
                        w_obj.x = vm.unwrap_i32(w_val)
                        return B.w_None
                    return W_OpImpl(w_setx)
                else:
                    return W_OpImpl.NULL
        # ========== /EXT module for this test =========

        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import MyClass

        @blue
        def get_hello():
            obj = MyClass()
            return obj.hello

        def get_x() -> i32:
            obj = MyClass()
            return obj.x

        def set_get_x() -> i32:
            obj = MyClass()
            obj.x = 123
            return obj.x
        """)
        assert mod.get_hello() == 'HELLO--42'
        assert mod.get_x() == 0
        assert mod.set_get_x() == 123
