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
    def w_new(vm: 'SPyVM', w_x: W_I32) -> 'W_MyClass':
        return W_MyClass(w_x)

    @builtin_method('__getitem__')
    @staticmethod
    def w_getitem(vm: 'SPyVM', w_obj: 'W_MyClass', w_i: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_obj.w_x)
        i = vm.unwrap_i32(w_i)
        return vm.wrap(x + i)  # type: ignore

    @builtin_method('__setitem__')
    @staticmethod
    def w_setitem(vm: 'SPyVM', w_obj: 'W_MyClass', w_i: W_I32,
                  w_v: W_I32) -> None:
        i = vm.unwrap_i32(w_i)
        v = vm.unwrap_i32(w_v)
        w_obj.w_x = vm.wrap(v - i)  # type: ignore

    @builtin_method('__call__')
    @staticmethod
    def w_call(vm: 'SPyVM', w_obj: 'W_MyClass', w_arg: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_obj.w_x)
        arg = vm.unwrap_i32(w_arg)
        return vm.wrap(x * arg)  # type: ignore

    @builtin_method('__call_method__')
    @staticmethod
    def w_call_method(vm: 'SPyVM', w_obj: 'W_MyClass', w_method: W_Str,
                      w_arg: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_obj.w_x)
        arg = vm.unwrap_i32(w_arg)
        method = vm.unwrap_str(w_method)
        if method == "add":
            return vm.wrap(x + arg)  # type: ignore
        elif method == "mul":
            return vm.wrap(x * arg)  # type: ignore
        return vm.wrap(-1)  # type: ignore

    @builtin_method('__getattr__')
    @staticmethod
    def w_getattr(vm: 'SPyVM', w_obj: 'W_MyClass', w_attr: W_Str) -> W_I32:
        x = vm.unwrap_i32(w_obj.w_x)
        attr = vm.unwrap_str(w_attr)
        if attr == "value":
            return vm.wrap(x)  # type: ignore
        elif attr == "double":
            return vm.wrap(x * 2)  # type: ignore
        return vm.wrap(-1)  # type: ignore

    @builtin_method('__setattr__')
    @staticmethod
    def w_setattr(vm: 'SPyVM', w_obj: 'W_MyClass', w_attr: W_Str,
                  w_v: W_I32) -> None:
        attr = vm.unwrap_str(w_attr)
        v = vm.unwrap_i32(w_v)
        if attr == "value":
            w_obj.w_x = vm.wrap(v)  # type: ignore
        elif attr == "double":
            w_obj.w_x = vm.wrap(v // 2)  # type: ignore
        return None


@no_C
class TestOperatorSimple(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def setup_ext(self) -> None:
        EXT = ModuleRegistry('ext')
        EXT.builtin_type('MyClass')(W_MyClass)
        self.vm.make_module(EXT)

    def test_getitem(self):
        self.setup_ext()
        src = """
        from ext import MyClass

        def foo(x: i32) -> i32:
            obj = MyClass(x)
            return obj[5]
        """
        mod = self.compile(src)
        assert mod.foo(4) == 9

    def test_setitem(self):
        self.setup_ext()
        src = """
        from ext import MyClass

        def foo(x: i32, v: i32) -> i32:
            obj = MyClass(x)
            obj[3] = v
            return obj[0]
        """
        mod = self.compile(src)
        assert mod.foo(10, 15) == 12  # obj.x = (v - i) = (15 - 3) = 12

    def test_call(self):
        self.setup_ext()
        src = """
        from ext import MyClass

        def foo(x: i32, arg: i32) -> i32:
            obj = MyClass(x)
            return obj(arg)
        """
        mod = self.compile(src)
        assert mod.foo(4, 3) == 12  # 4 * 3 = 12

    def test_call_method(self):
        self.setup_ext()
        src = """
        from ext import MyClass

        def foo(x: i32, arg: i32) -> i32:
            obj = MyClass(x)
            return obj.add(arg)

        def bar(x: i32, arg: i32) -> i32:
            obj = MyClass(x)
            return obj.mul(arg)
        """
        mod = self.compile(src)
        assert mod.foo(4, 3) == 7   # 4 + 3 = 7
        assert mod.bar(4, 3) == 12  # 4 * 3 = 12

    def test_getattr(self):
        self.setup_ext()
        src = """
        from ext import MyClass

        def foo(x: i32) -> i32:
            obj = MyClass(x)
            return obj.value

        def bar(x: i32) -> i32:
            obj = MyClass(x)
            return obj.double
        """
        mod = self.compile(src)
        assert mod.foo(4) == 4
        assert mod.bar(4) == 8  # 4 * 2 = 8

    def test_setattr(self):
        self.setup_ext()
        src = """
        from ext import MyClass

        def foo(x: i32, v: i32) -> i32:
            obj = MyClass(x)
            obj.value = v
            return obj.value

        def bar(x: i32, v: i32) -> i32:
            obj = MyClass(x)
            obj.double = v
            return obj.value
        """
        mod = self.compile(src)
        assert mod.foo(4, 7) == 7
        assert mod.bar(4, 10) == 5  # v // 2 = 10 // 2 = 5
