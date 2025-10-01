from typing import Any
from spy.vm.primitive import W_I32
from spy.vm.builtin import builtin_method
from spy.vm.w import W_Object
from spy.vm.opspec import W_OpSpec, W_MetaArg
from spy.vm.registry import ModuleRegistry
from spy.vm.vm import SPyVM
from spy.tests.support import CompilerTest, no_C

class W_BinOpClass(W_Object):

    def __init__(self, w_x: W_I32) -> None:
        self.w_x = w_x

    @builtin_method('__new__')
    @staticmethod
    def w_new(vm: 'SPyVM', w_x: W_I32) -> 'W_BinOpClass':
        return W_BinOpClass(w_x)

    @builtin_method('__add__')
    @staticmethod
    def w_add(vm: 'SPyVM', w_self: 'W_BinOpClass', w_other: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_self.w_x)
        other = vm.unwrap_i32(w_other)
        return vm.wrap(x + other)

    @builtin_method('__sub__')
    @staticmethod
    def w_sub(vm: 'SPyVM', w_self: 'W_BinOpClass', w_other: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_self.w_x)
        other = vm.unwrap_i32(w_other)
        return vm.wrap(x - other)

    @builtin_method('__mul__')
    @staticmethod
    def w_mul(vm: 'SPyVM', w_self: 'W_BinOpClass', w_other: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_self.w_x)
        other = vm.unwrap_i32(w_other)
        return vm.wrap(x * other)

    @builtin_method('__div__')
    @staticmethod
    def w_div(vm: 'SPyVM', w_self: 'W_BinOpClass', w_other: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_self.w_x)
        other = vm.unwrap_i32(w_other)
        return vm.wrap(x // other)

    @builtin_method('__mod__')
    @staticmethod
    def w_mod(vm: 'SPyVM', w_self: 'W_BinOpClass', w_other: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_self.w_x)
        other = vm.unwrap_i32(w_other)
        return vm.wrap(x % other)

    @builtin_method('__and__')
    @staticmethod
    def w_and(vm: 'SPyVM', w_self: 'W_BinOpClass', w_other: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_self.w_x)
        other = vm.unwrap_i32(w_other)
        return vm.wrap(x & other)

    @builtin_method('__or__')
    @staticmethod
    def w_or(vm: 'SPyVM', w_self: 'W_BinOpClass', w_other: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_self.w_x)
        other = vm.unwrap_i32(w_other)
        return vm.wrap(x | other)

    @builtin_method('__xor__')
    @staticmethod
    def w_xor(vm: 'SPyVM', w_self: 'W_BinOpClass', w_other: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_self.w_x)
        other = vm.unwrap_i32(w_other)
        return vm.wrap(x ^ other)

    @builtin_method('__lshift__')
    @staticmethod
    def w_shl(vm: 'SPyVM', w_self: 'W_BinOpClass', w_other: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_self.w_x)
        other = vm.unwrap_i32(w_other)
        return vm.wrap(x << other)

    @builtin_method('__rshift__')
    @staticmethod
    def w_shr(vm: 'SPyVM', w_self: 'W_BinOpClass', w_other: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_self.w_x)
        other = vm.unwrap_i32(w_other)
        return vm.wrap(x >> other)

    @builtin_method('__eq__')
    @staticmethod
    def w_eq(vm: 'SPyVM', w_self: 'W_BinOpClass', w_other: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_self.w_x)
        other = vm.unwrap_i32(w_other)
        return vm.wrap(1 if x == other else 0)

    @builtin_method('__ne__')
    @staticmethod
    def w_ne(vm: 'SPyVM', w_self: 'W_BinOpClass', w_other: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_self.w_x)
        other = vm.unwrap_i32(w_other)
        return vm.wrap(1 if x != other else 0)

    @builtin_method('__lt__')
    @staticmethod
    def w_lt(vm: 'SPyVM', w_self: 'W_BinOpClass', w_other: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_self.w_x)
        other = vm.unwrap_i32(w_other)
        return vm.wrap(1 if x < other else 0)

    @builtin_method('__le__')
    @staticmethod
    def w_le(vm: 'SPyVM', w_self: 'W_BinOpClass', w_other: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_self.w_x)
        other = vm.unwrap_i32(w_other)
        return vm.wrap(1 if x <= other else 0)

    @builtin_method('__gt__')
    @staticmethod
    def w_gt(vm: 'SPyVM', w_self: 'W_BinOpClass', w_other: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_self.w_x)
        other = vm.unwrap_i32(w_other)
        return vm.wrap(1 if x > other else 0)

    @builtin_method('__ge__')
    @staticmethod
    def w_ge(vm: 'SPyVM', w_self: 'W_BinOpClass', w_other: W_I32) -> W_I32:
        x = vm.unwrap_i32(w_self.w_x)
        other = vm.unwrap_i32(w_other)
        return vm.wrap(1 if x >= other else 0)


class W_MyInt(W_Object):
    """
    Simulate a value type, so we can test that __eq__ and __new__ are
    automatically generated.
    """
    __spy_storage_category__ = 'value'

    def __init__(self, val: int) -> None:
        self.val = val

    @builtin_method('__new__')
    @staticmethod
    def w_new(vm: 'SPyVM', w_x: W_I32) -> 'W_MyInt':
        val = int(vm.unwrap_i32(w_x))
        return W_MyInt(val)

    def spy_key(self, vm: 'SPyVM') -> Any:
        return ('MyInt', self.val)



@no_C
class TestOperatorBinop(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def setup_ext(self) -> None:
        EXT = ModuleRegistry('ext')
        EXT.builtin_type('BinOpClass')(W_BinOpClass)
        EXT.builtin_type('MyInt')(W_MyInt)
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

    def test_eq_ne(self):
        self.setup_ext()
        src = """
        from ext import BinOpClass

        def test_eq(x: i32, y: i32) -> i32:
            obj = BinOpClass(x)
            return obj == y

        def test_ne(x: i32, y: i32) -> i32:
            obj = BinOpClass(x)
            return obj != y
        """
        mod = self.compile(src)
        assert mod.test_eq(5, 5) == 1   # 5 == 5 is True (1)
        assert mod.test_eq(5, 6) == 0   # 5 == 6 is False (0)
        assert mod.test_ne(5, 5) == 0   # 5 != 5 is False (0)
        assert mod.test_ne(5, 6) == 1   # 5 != 6 is True (1)

    def test_lt_le(self):
        self.setup_ext()
        src = """
        from ext import BinOpClass

        def test_lt(x: i32, y: i32) -> i32:
            obj = BinOpClass(x)
            return obj < y

        def test_le(x: i32, y: i32) -> i32:
            obj = BinOpClass(x)
            return obj <= y
        """
        mod = self.compile(src)
        assert mod.test_lt(5, 6) == 1   # 5 < 6 is True (1)
        assert mod.test_lt(6, 5) == 0   # 6 < 5 is False (0)
        assert mod.test_lt(5, 5) == 0   # 5 < 5 is False (0)

        assert mod.test_le(5, 6) == 1   # 5 <= 6 is True (1)
        assert mod.test_le(6, 5) == 0   # 6 <= 5 is False (0)
        assert mod.test_le(5, 5) == 1   # 5 <= 5 is True (1)

    def test_gt_ge(self):
        self.setup_ext()
        src = """
        from ext import BinOpClass

        def test_gt(x: i32, y: i32) -> i32:
            obj = BinOpClass(x)
            return obj > y

        def test_ge(x: i32, y: i32) -> i32:
            obj = BinOpClass(x)
            return obj >= y
        """
        mod = self.compile(src)
        assert mod.test_gt(6, 5) == 1   # 6 > 5 is True (1)
        assert mod.test_gt(5, 6) == 0   # 5 > 6 is False (0)
        assert mod.test_gt(5, 5) == 0   # 5 > 5 is False (0)

        assert mod.test_ge(6, 5) == 1   # 6 >= 5 is True (1)
        assert mod.test_ge(5, 6) == 0   # 5 >= 6 is False (0)
        assert mod.test_ge(5, 5) == 1   # 5 >= 5 is True (1)

    def test_automatic_eq_ne(self):
        self.setup_ext()
        src = """
        from ext import MyInt

        def eq(x: i32, y: i32) -> bool:
            x1 = MyInt(x)
            y1 = MyInt(y)
            return x1 == y1

        def ne(x: i32, y: i32) -> bool:
            x1 = MyInt(x)
            y1 = MyInt(y)
            return x1 != y1
        """
        mod = self.compile(src)
        assert mod.eq(5, 5) == True    # 5 == 5 is True
        assert mod.eq(5, 6) == False   # 5 == 6 is False
        assert mod.ne(5, 5) == False   # 5 != 5 is False
        assert mod.ne(5, 6) == True    # 5 != 6 is True
