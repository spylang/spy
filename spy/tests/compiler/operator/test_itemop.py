from spy.vm.primitive import W_I32
from spy.vm.builtin import builtin_func, builtin_method
from spy.vm.w import W_Object
from spy.vm.opspec import W_OpSpec, W_OpArg
from spy.vm.registry import ModuleRegistry
from spy.vm.vm import SPyVM
from spy.tests.support import CompilerTest, no_C


class W_MyClass(W_Object):
    def __init__(self, w_base: W_I32) -> None:
        self.w_base = w_base
        self.w_values: dict[W_I32, W_I32] = {}

    @builtin_method('__new__')
    @staticmethod
    def w_new(vm: 'SPyVM', w_base: W_I32) -> 'W_MyClass':
        return W_MyClass(w_base)

    @builtin_method('__getitem__', color='blue', kind='metafunc')
    @staticmethod
    def w_GETITEM(vm: 'SPyVM', wop_self: W_OpArg, wop_i: W_OpArg) -> W_OpSpec:

        @builtin_func('ext')
        def w_getitem(vm: 'SPyVM', w_self: W_MyClass, w_i: W_I32) -> W_I32:
            base = vm.unwrap_i32(w_self.w_base)
            idx = vm.unwrap_i32(w_i)

            # If index exists in dictionary, return that value
            if idx in w_self.w_values:
                return w_self.w_values[idx]

            # Otherwise calculate a value based on base and index
            return vm.wrap(base + idx)  # type: ignore

        return W_OpSpec(w_getitem)

    @builtin_method('__setitem__', color='blue', kind='metafunc')
    @staticmethod
    def w_SETITEM(vm: 'SPyVM', wop_self: W_OpArg, wop_i: W_OpArg,
                  wop_v: W_OpArg) -> W_OpSpec:

        @builtin_func('ext')
        def w_setitem(vm: 'SPyVM', w_self: W_MyClass, w_i: W_I32,
                      w_v: W_I32) -> None:
            idx = vm.unwrap_i32(w_i)
            w_self.w_values[idx] = w_v

        return W_OpSpec(w_setitem)


class W_2DArray(W_Object):
    "Simple 2D array of fixed size 3x3"
    W = 3
    H = 3

    def __init__(self) -> None:
        self.data = [0] * (self.W * self.H)

    @builtin_method('__new__')
    @staticmethod
    def w_new(vm: 'SPyVM') -> 'W_2DArray':
        return W_2DArray()

    @builtin_method('__getitem__', color='blue', kind='metafunc')
    @staticmethod
    def w_GETITEM(vm: 'SPyVM', wop_self: W_OpArg,
                  wop_i: W_OpArg, wop_j: W_OpArg) -> W_OpSpec:
        @builtin_func('ext')
        def w_getitem(vm: 'SPyVM', w_self: W_2DArray,
                      w_i: W_I32, w_j: W_I32) -> W_I32:
            i = vm.unwrap_i32(w_i)
            j = vm.unwrap_i32(w_j)
            k = i + (j * w_self.W)
            val = w_self.data[k]
            return vm.wrap(val)  # type: ignore
        return W_OpSpec(w_getitem)

    @builtin_method('__setitem__', color='blue', kind='metafunc')
    @staticmethod
    def w_SETITEM(vm: 'SPyVM', wop_self: W_OpArg, wop_i: W_OpArg,
                  wop_j: W_OpArg, wop_v: W_OpArg) -> W_OpSpec:
        @builtin_func('ext')
        def w_setitem(vm: 'SPyVM', w_self: W_2DArray, w_i: W_I32,
                      w_j: W_I32, w_v: W_I32) -> None:
            i = vm.unwrap_i32(w_i)
            j = vm.unwrap_i32(w_j)
            v = vm.unwrap_i32(w_v)
            k = i + (j * w_self.W)
            w_self.data[k] = v
        return W_OpSpec(w_setitem)



@no_C
class TestItemop(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def setup_ext(self) -> None:
        EXT = ModuleRegistry('ext')
        EXT.builtin_type('MyClass')(W_MyClass)
        EXT.builtin_type('W_2DArray')(W_2DArray)
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

    def test_2darray(self):
        self.setup_ext()
        src = """
        from ext import W_2DArray

        def set_and_get(i: i32, j: i32, val: i32) -> i32:
            arr = W_2DArray()
            arr[i, j] = val
            return arr[i, j]

        def get_default(i: i32, j: i32) -> i32:
            arr = W_2DArray()
            return arr[i, j]
        """
        mod = self.compile(src)
        assert mod.set_and_get(1, 1, 42) == 42
        assert mod.set_and_get(0, 2, 24) == 24
        assert mod.set_and_get(2, 1, 99) == 99
        assert mod.get_default(1, 2) == 0
