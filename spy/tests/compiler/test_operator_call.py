from typing import Annotated
import pytest
from spy.vm.primitive import W_I32, W_Dynamic, W_Void
from spy.vm.b import B
from spy.vm.object import Member
from spy.vm.builtin import builtin_func, builtin_type
from spy.vm.w import W_Type, W_Object, W_Str, W_List
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.registry import ModuleRegistry
from spy.vm.vm import SPyVM
from spy.vm.list import W_List
from spy.tests.support import CompilerTest, no_C

@no_C
class TestCallOp(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def test_call_instance(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext')

        @EXT.builtin_type('Adder')
        class W_Adder(W_Object):

            def __init__(self, x: int) -> None:
                self.x = x

            @staticmethod
            def w_spy_new(vm: 'SPyVM', w_cls: W_Type, w_x: W_I32) -> 'W_Adder':
                return W_Adder(vm.unwrap_i32(w_x))

            @staticmethod
            def op_CALL(vm: 'SPyVM', wop_obj: W_OpArg,
                        w_opargs: W_List[W_OpArg]) -> W_OpImpl:
                @builtin_func('ext')
                def w_call(vm: 'SPyVM', w_obj: W_Adder, w_y: W_I32) -> W_I32:
                    y = vm.unwrap_i32(w_y)
                    res = w_obj.x + y
                    return vm.wrap(res) # type: ignore
                return W_OpImpl(w_call)
        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import Adder

        def foo(x: i32, y: i32) -> i32:
            obj = Adder(x)
            return obj(y)
        """)
        x = mod.foo(5, 7)
        assert x == 12


    def test_call_type(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext')

        @EXT.builtin_type('Point')
        class W_Point(W_Object):
            w_x: Annotated[W_I32, Member('x')]
            w_y: Annotated[W_I32, Member('y')]

            def __init__(self, w_x: W_I32, w_y: W_I32) -> None:
                self.w_x = w_x
                self.w_y = w_y

            @staticmethod
            def meta_op_CALL(vm: 'SPyVM', w_type: W_Type,
                             w_argtypes: W_Dynamic) -> W_OpImpl:
                @builtin_func('ext')
                def w_new(vm: 'SPyVM', w_cls: W_Type,
                        w_x: W_I32, w_y: W_I32) -> W_Point:
                    return W_Point(w_x, w_y)
                return W_OpImpl(w_new)
        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import Point

        @blue
        def foo(x: i32, y: i32) -> i32:
            p = Point(x, y)
            return p.x * 10 + p.y
        """)
        res = mod.foo(3, 6)
        assert res == 36

    def test_spy_new(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext')

        @EXT.builtin_type('Point')
        class W_Point(W_Object):
            w_x: Annotated[W_I32, Member('x')]
            w_y: Annotated[W_I32, Member('y')]

            def __init__(self, w_x: W_I32, w_y: W_I32) -> None:
                self.w_x = w_x
                self.w_y = w_y

            @staticmethod
            def w_spy_new(vm: 'SPyVM', w_cls: W_Type,
                        w_x: W_I32, w_y: W_I32) -> 'W_Point':
                return W_Point(w_x, w_y)
        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import Point

        @blue
        def foo(x: i32, y: i32) -> i32:
            p = Point(x, y)
            return p.x * 10 + p.y
        """)
        res = mod.foo(3, 6)
        assert res == 36


    def test_call_method(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext')

        @EXT.builtin_type('Calc')
        class W_Calc(W_Object):

            def __init__(self, x: int) -> None:
                self.x = x

            @staticmethod
            def w_spy_new(vm: 'SPyVM', w_cls: W_Type, w_x: W_I32) -> 'W_Calc':
                return W_Calc(vm.unwrap_i32(w_x))

            @staticmethod
            def op_CALL_METHOD(vm: 'SPyVM', wop_obj: W_OpArg,
                               wop_method: W_OpArg,
                               w_opargs: W_List[W_OpArg]) -> W_OpImpl:
                meth = wop_method.blue_unwrap_str(vm)
                if meth == 'add':
                    @builtin_func('ext', 'add')
                    def w_fn(vm: 'SPyVM', w_self: W_Calc,
                             w_arg: W_I32) -> W_I32:
                        y = vm.unwrap_i32(w_arg)
                        return vm.wrap(w_self.x + y)  # type: ignore
                    return W_OpImpl(w_fn, [wop_obj] + w_opargs.items_w)

                elif meth == 'sub':
                    @builtin_func('ext', 'sub')
                    def w_fn(vm: 'SPyVM', w_self: W_Calc,
                             w_arg: W_I32) -> W_I32:
                        y = vm.unwrap_i32(w_arg)
                        return vm.wrap(w_self.x - y)  # type: ignore
                    return W_OpImpl(w_fn, [wop_obj] + w_opargs.items_w)
                else:
                    return W_OpImpl.NULL
        # ========== /EXT module for this test =========

        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import Calc

        def foo(x: i32, y: i32, z: i32) -> i32:
            obj = Calc(x)
            return obj.add(y) * 10 + obj.sub(z)
        """)
        x = mod.foo(5, 1, 2)
        assert x == 63
