from spy.vm.primitive import W_I32
from spy.vm.builtin import builtin_func, builtin_method
from spy.vm.w import W_Object
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.registry import ModuleRegistry
from spy.vm.vm import SPyVM
from spy.tests.support import CompilerTest, no_C


class W_MySequence(W_Object):
    """A custom class that supports len() operation."""

    def __init__(self, w_size: W_I32) -> None:
        self.w_size = w_size

    @builtin_method('__new__')
    @staticmethod
    def w_new(vm: 'SPyVM', w_size: W_I32) -> 'W_MySequence':
        return W_MySequence(w_size)

    @builtin_method('__LEN__', color='blue')
    @staticmethod
    def w_LEN(vm: 'SPyVM', wop_self: W_OpArg) -> W_OpImpl:
        @builtin_func('ext')
        def w_len(vm: 'SPyVM', w_self: W_MySequence) -> W_I32:
            return w_self.w_size
        return W_OpImpl(w_len)



class TestBuiltins(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def setup_ext(self) -> None:
        EXT = ModuleRegistry('ext')
        EXT.builtin_type('MySequence')(W_MySequence)
        self.vm.make_module(EXT)

    @no_C
    def test_LEN(self):
        self.setup_ext()
        src = """
        from ext import MySequence

        def foo(size: i32) -> i32:
            obj = MySequence(size)
            return len(obj)
        """
        mod = self.compile(src)
        assert mod.foo(5) == 5
        assert mod.foo(42) == 42
        assert mod.foo(0) == 0
