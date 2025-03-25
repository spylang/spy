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

# BinOpClass with uppercase binary operators
class W_BinOpClass(W_Object):

    def __init__(self, w_x: W_I32) -> None:
        self.w_x = w_x

    @builtin_method('__new__')
    @staticmethod
    def w_new(vm: 'SPyVM', w_x: W_I32) -> 'W_BinOpClass':
        return W_BinOpClass(w_x)

    @builtin_method('__ADD__', color='blue')
    @staticmethod
    def w_ADD(vm: 'SPyVM', wop_self: W_OpArg, wop_other: W_OpArg) -> W_OpImpl:
        @builtin_func('ext')
        def w_add(vm: 'SPyVM', w_self: W_BinOpClass, w_other: W_I32) -> W_I32:
            x = vm.unwrap_i32(w_self.w_x)
            other = vm.unwrap_i32(w_other)
            return vm.wrap(x + other)  # type: ignore
        return W_OpImpl(w_add)

    @builtin_method('__SUB__', color='blue')
    @staticmethod
    def w_SUB(vm: 'SPyVM', wop_self: W_OpArg, wop_other: W_OpArg) -> W_OpImpl:
        @builtin_func('ext')
        def w_sub(vm: 'SPyVM', w_self: W_BinOpClass, w_other: W_I32) -> W_I32:
            x = vm.unwrap_i32(w_self.w_x)
            other = vm.unwrap_i32(w_other)
            return vm.wrap(x - other)  # type: ignore
        return W_OpImpl(w_sub)

    @builtin_method('__MUL__', color='blue')
    @staticmethod
    def w_MUL(vm: 'SPyVM', wop_self: W_OpArg, wop_other: W_OpArg) -> W_OpImpl:
        @builtin_func('ext')
        def w_mul(vm: 'SPyVM', w_self: W_BinOpClass, w_other: W_I32) -> W_I32:
            x = vm.unwrap_i32(w_self.w_x)
            other = vm.unwrap_i32(w_other)
            return vm.wrap(x * other)  # type: ignore
        return W_OpImpl(w_mul)

    @builtin_method('__DIV__', color='blue')
    @staticmethod
    def w_DIV(vm: 'SPyVM', wop_self: W_OpArg, wop_other: W_OpArg) -> W_OpImpl:
        @builtin_func('ext')
        def w_div(vm: 'SPyVM', w_self: W_BinOpClass, w_other: W_I32) -> W_I32:
            x = vm.unwrap_i32(w_self.w_x)
            other = vm.unwrap_i32(w_other)
            return vm.wrap(x // other)  # type: ignore
        return W_OpImpl(w_div)

    @builtin_method('__MOD__', color='blue')
    @staticmethod
    def w_MOD(vm: 'SPyVM', wop_self: W_OpArg, wop_other: W_OpArg) -> W_OpImpl:
        @builtin_func('ext')
        def w_mod(vm: 'SPyVM', w_self: W_BinOpClass, w_other: W_I32) -> W_I32:
            x = vm.unwrap_i32(w_self.w_x)
            other = vm.unwrap_i32(w_other)
            return vm.wrap(x % other)  # type: ignore
        return W_OpImpl(w_mod)

    @builtin_method('__AND__', color='blue')
    @staticmethod
    def w_AND(vm: 'SPyVM', wop_self: W_OpArg, wop_other: W_OpArg) -> W_OpImpl:
        @builtin_func('ext')
        def w_and(vm: 'SPyVM', w_self: W_BinOpClass, w_other: W_I32) -> W_I32:
            x = vm.unwrap_i32(w_self.w_x)
            other = vm.unwrap_i32(w_other)
            return vm.wrap(x & other)  # type: ignore
        return W_OpImpl(w_and)

    @builtin_method('__OR__', color='blue')
    @staticmethod
    def w_OR(vm: 'SPyVM', wop_self: W_OpArg, wop_other: W_OpArg) -> W_OpImpl:
        @builtin_func('ext')
        def w_or(vm: 'SPyVM', w_self: W_BinOpClass, w_other: W_I32) -> W_I32:
            x = vm.unwrap_i32(w_self.w_x)
            other = vm.unwrap_i32(w_other)
            return vm.wrap(x | other)  # type: ignore
        return W_OpImpl(w_or)

    @builtin_method('__XOR__', color='blue')
    @staticmethod
    def w_XOR(vm: 'SPyVM', wop_self: W_OpArg, wop_other: W_OpArg) -> W_OpImpl:
        @builtin_func('ext')
        def w_xor(vm: 'SPyVM', w_self: W_BinOpClass, w_other: W_I32) -> W_I32:
            x = vm.unwrap_i32(w_self.w_x)
            other = vm.unwrap_i32(w_other)
            return vm.wrap(x ^ other)  # type: ignore
        return W_OpImpl(w_xor)

    @builtin_method('__SHL__', color='blue')
    @staticmethod
    def w_SHL(vm: 'SPyVM', wop_self: W_OpArg, wop_other: W_OpArg) -> W_OpImpl:
        @builtin_func('ext')
        def w_shl(vm: 'SPyVM', w_self: W_BinOpClass, w_other: W_I32) -> W_I32:
            x = vm.unwrap_i32(w_self.w_x)
            other = vm.unwrap_i32(w_other)
            return vm.wrap(x << other)  # type: ignore
        return W_OpImpl(w_shl)

    @builtin_method('__SHR__', color='blue')
    @staticmethod
    def w_SHR(vm: 'SPyVM', wop_self: W_OpArg, wop_other: W_OpArg) -> W_OpImpl:
        @builtin_func('ext')
        def w_shr(vm: 'SPyVM', w_self: W_BinOpClass, w_other: W_I32) -> W_I32:
            x = vm.unwrap_i32(w_self.w_x)
            other = vm.unwrap_i32(w_other)
            return vm.wrap(x >> other)  # type: ignore
        return W_OpImpl(w_shr)


@no_C
class TestOperatorBinop(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def setup_ext(self) -> None:
        EXT = ModuleRegistry('ext')
        EXT.builtin_type('BinOpClass')(W_BinOpClass)
        self.vm.make_module(EXT)

    def test_add(self):
        self.setup_ext()
        src = """
        from ext import BinOpClass

        def foo(x: i32, y: i32) -> i32:
            obj = BinOpClass(x)
            return obj + y
        """
        mod = self.compile(src)
        assert mod.foo(4, 5) == 9  # 4 + 5 = 9

    def test_sub(self):
        self.setup_ext()
        src = """
        from ext import BinOpClass

        def foo(x: i32, y: i32) -> i32:
            obj = BinOpClass(x)
            return obj - y
        """
        mod = self.compile(src)
        assert mod.foo(10, 3) == 7  # 10 - 3 = 7

    def test_mul(self):
        self.setup_ext()
        src = """
        from ext import BinOpClass

        def foo(x: i32, y: i32) -> i32:
            obj = BinOpClass(x)
            return obj * y
        """
        mod = self.compile(src)
        assert mod.foo(4, 3) == 12  # 4 * 3 = 12

    def test_div(self):
        self.setup_ext()
        src = """
        from ext import BinOpClass

        def foo(x: i32, y: i32) -> i32:
            obj = BinOpClass(x)
            return obj / y
        """
        mod = self.compile(src)
        assert mod.foo(10, 2) == 5  # 10 // 2 = 5

    def test_mod(self):
        self.setup_ext()
        src = """
        from ext import BinOpClass

        def foo(x: i32, y: i32) -> i32:
            obj = BinOpClass(x)
            return obj % y
        """
        mod = self.compile(src)
        assert mod.foo(10, 3) == 1  # 10 % 3 = 1

    def test_bitwise_ops(self):
        self.setup_ext()
        src = """
        from ext import BinOpClass

        def test_and(x: i32, y: i32) -> i32:
            obj = BinOpClass(x)
            return obj & y
            
        def test_or(x: i32, y: i32) -> i32:
            obj = BinOpClass(x)
            return obj | y
            
        def test_xor(x: i32, y: i32) -> i32:
            obj = BinOpClass(x)
            return obj ^ y
        """
        mod = self.compile(src)
        assert mod.test_and(12, 5) == 4   # 1100 & 0101 = 0100 = 4
        assert mod.test_or(12, 5) == 13   # 1100 | 0101 = 1101 = 13
        assert mod.test_xor(12, 5) == 9   # 1100 ^ 0101 = 1001 = 9

    def test_shift_ops(self):
        self.setup_ext()
        src = """
        from ext import BinOpClass

        def test_shl(x: i32, y: i32) -> i32:
            obj = BinOpClass(x)
            return obj << y
            
        def test_shr(x: i32, y: i32) -> i32:
            obj = BinOpClass(x)
            return obj >> y
        """
        mod = self.compile(src)
        assert mod.test_shl(5, 2) == 20   # 5 << 2 = 20
        assert mod.test_shr(20, 2) == 5   # 20 >> 2 = 5