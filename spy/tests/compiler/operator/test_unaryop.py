# write test for unary neg

from spy.vm.primitive import W_I32
from spy.vm.builtin import builtin_method
from spy.vm.w import W_Object
from spy.vm.opspec import W_OpSpec, W_MetaArg
from spy.vm.registry import ModuleRegistry
from spy.vm.vm import SPyVM
from spy.tests.support import CompilerTest, no_C

class W_MyClass(W_Object):

    def __init__(self, w_x: W_I32) -> None:
        self.w_x = w_x

    @builtin_method('__new__')
    @staticmethod
    def w_new(vm: 'SPyVM', w_x: W_I32) -> 'W_MyClass':
        return W_MyClass(w_x)

    @builtin_method('__neg__')
    @staticmethod
    def w_neg(vm: 'SPyVM', w_self: 'W_MyClass') -> W_I32:
        x = vm.unwrap_i32(w_self.w_x)
        return vm.wrap(-x)


@no_C
class TestOperatorUnaryOp(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def setup_ext(self) -> None:
        EXT = ModuleRegistry('ext')
        EXT.builtin_type('MyClass')(W_MyClass)
        self.vm.make_module(EXT)

    def test_neg(self):
        self.setup_ext()
        src = """
        from ext import MyClass

        def foo(x: i32) -> i32:
            obj = MyClass(x)
            return -obj
        """
        mod = self.compile(src)
        assert mod.foo(5) == -5
        assert mod.foo(-10) == 10
        assert mod.foo(0) == 0
