from typing import Annotated
import pytest
from spy.vm.primitive import W_I32
from spy.vm.b import B
from spy.vm.object import Member
from spy.vm.builtin import (builtin_func, builtin_method, builtin_class_attr,
                            builtin_property)
from spy.vm.w import W_Object, W_Str
from spy.vm.opspec import W_OpSpec, W_OpArg
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

            @builtin_method('__new__')
            @staticmethod
            def w_new(vm: 'SPyVM') -> 'W_MyClass':
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

    def test_descriptor_get(self):
        # ========== EXT module for this test ==========
        w_hello: W_Str = self.vm.wrap('hello')  # type: ignore
        EXT = ModuleRegistry('ext')

        @EXT.builtin_type('MyProxy')
        class W_MyProxy(W_Object):
            w_val: W_Str

            def __init__(self, w_val: W_Str) -> None:
                self.w_val = w_val

            @builtin_method('__get__')
            @staticmethod
            def w_get(vm: 'SPyVM', w_self: 'W_MyProxy',
                      w_obj: W_Object) -> W_Str:
                return w_self.w_val

        @EXT.builtin_type('MyClass')
        class W_MyClass(W_Object):
            w_x = builtin_class_attr('x', W_MyProxy(w_hello))

            @builtin_method('__new__')
            @staticmethod
            def w_new(vm: 'SPyVM') -> 'W_MyClass':
                return W_MyClass()

        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import MyClass

        @blue
        def foo() -> str:
            obj =  MyClass()
            return obj.x
        """)
        x = mod.foo()
        assert x == 'hello'

    def test_instance_property(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext')

        @EXT.builtin_type('MyClass')
        class W_MyClass(W_Object):

            def __init__(self, x: int) -> None:
                self.x = x

            @builtin_method('__new__')
            @staticmethod
            def w_new(vm: 'SPyVM', w_x: W_I32) -> 'W_MyClass':
                x = vm.unwrap_i32(w_x)
                return W_MyClass(x)

            @builtin_property('x')
            @staticmethod
            def w_get_x(vm: 'SPyVM', w_self: 'W_MyClass') -> W_I32:
                return vm.wrap(w_self.x)  # type: ignore

            @builtin_property('x2', color='blue', kind='metafunc')
            @staticmethod
            def w_GET_x2(vm: 'SPyVM', wop_self: 'W_OpArg') -> W_OpSpec:
                """
                This exist just to test that we can have a metafunc as a
                @builtin_property
                """
                w_t = wop_self.w_static_type
                assert W_MyClass._w is w_t
                @builtin_func(w_t.fqn, 'get_y')
                def w_get_x2(vm: 'SPyVM', w_self: W_MyClass) -> W_I32:
                    return vm.wrap(w_self.x * 2)  # type: ignore
                return W_OpSpec(w_get_x2, [wop_self])


        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile(
                """
        from ext import MyClass

        @blue
        def get_x():
            obj = MyClass(42)
            return obj.x

        @blue
        def get_x2():
            obj = MyClass(43)
            return obj.x2
        """)
        x = mod.get_x()
        assert x == 42
        x2 = mod.get_x2()
        assert x2 == 86


    @pytest.mark.skip(reason='implement me')
    def test_class_property(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext')

        @EXT.builtin_type('MyClass')
        class W_MyClass(W_Object):

            @builtin_method('__new__')
            @staticmethod
            def w_new(vm: 'SPyVM') -> 'W_MyClass':
                return W_MyClass()

            @builtin_property('NULL', color='blue', kind='metafunc')
            @staticmethod
            def w_GET_NULL(vm: 'SPyVM', wop_self: 'W_OpArg') -> W_OpSpec:
                raise NotImplementedError('WIP')


        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile(
                """
        from ext import MyClass

        @blue
        def get_NULL():
            return MyClass.NULL

        """)
        x = mod.get_NULL()
        breakpoint()

    def test_getattr_setattr_custom(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext')

        @EXT.builtin_type('MyClass')
        class W_MyClass(W_Object):

            def __init__(self) -> None:
                self.x = 0

            @builtin_method('__new__')
            @staticmethod
            def w_new(vm: 'SPyVM') -> 'W_MyClass':
                return W_MyClass()

            @builtin_method('__getattr__', color='blue', kind='metafunc')
            @staticmethod
            def w_GETATTR(vm: 'SPyVM', wop_obj: W_OpArg,
                          wop_attr: W_OpArg) -> W_OpSpec:
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
                return W_OpSpec(w_fn)

            @builtin_method('__setattr__', color='blue', kind='metafunc')
            @staticmethod
            def w_SETATTR(vm: 'SPyVM', wop_obj: W_OpArg, wop_attr: W_OpArg,
                          wop_v: W_OpArg) -> W_OpSpec:
                attr = wop_attr.blue_unwrap_str(vm)
                if attr == 'x':
                    @builtin_func('ext')
                    def w_setx(vm: 'SPyVM', w_obj: W_MyClass,
                               w_attr: W_Str, w_val: W_I32) -> None:
                        w_obj.x = vm.unwrap_i32(w_val)
                    return W_OpSpec(w_setx)
                else:
                    return W_OpSpec.NULL
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
