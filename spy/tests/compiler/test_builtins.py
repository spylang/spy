from spy.vm.primitive import W_I32
from spy.vm.builtin import builtin_func, builtin_method
from spy.vm.w import W_Object
from spy.vm.opspec import W_OpSpec, W_OpArg
from spy.vm.registry import ModuleRegistry
from spy.vm.vm import SPyVM
from spy.tests.support import CompilerTest, no_C, expect_errors


class W_SeqLen(W_Object):
    """A custom class which implements __len__ as func"""

    def __init__(self, w_size: W_I32) -> None:
        self.w_size = w_size

    @builtin_method('__new__')
    @staticmethod
    def w_new(vm: 'SPyVM', w_size: W_I32) -> 'W_SeqLen':
        return W_SeqLen(w_size)

    @builtin_method('__len__')
    @staticmethod
    def w_len(vm: 'SPyVM', w_self: 'W_SeqLen') -> W_I32:
        return w_self.w_size


class W_SeqMetaLen(W_Object):
    """A custom class which implements __len__ as metafunc"""

    def __init__(self, w_size: W_I32) -> None:
        self.w_size = w_size

    @builtin_method('__new__')
    @staticmethod
    def w_new(vm: 'SPyVM', w_size: W_I32) -> 'W_SeqMetaLen':
        return W_SeqMetaLen(w_size)

    @builtin_method('__len__', color='blue', kind='metafunc')
    @staticmethod
    def w_LEN(vm: 'SPyVM', wop_self: W_OpArg) -> W_OpSpec:
        @builtin_func('ext')
        def w_len(vm: 'SPyVM', w_self: W_SeqMetaLen) -> W_I32:
            return w_self.w_size
        return W_OpSpec(w_len)



class TestBuiltins(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def setup_ext(self) -> None:
        EXT = ModuleRegistry('ext')
        EXT.builtin_type('SeqLen')(W_SeqLen)
        EXT.builtin_type('SeqMetaLen')(W_SeqMetaLen)
        self.vm.make_module(EXT)

    @no_C
    def test_len(self):
        self.setup_ext()
        src = """
        from ext import SeqLen

        def foo(size: i32) -> i32:
            obj = SeqLen(size)
            return len(obj)
        """
        mod = self.compile(src)
        assert mod.foo(5) == 5
        assert mod.foo(42) == 42
        assert mod.foo(0) == 0

    @no_C
    def test_len_metafunc(self):
        self.setup_ext()
        src = """
        from ext import SeqMetaLen

        def foo(size: i32) -> i32:
            obj = SeqMetaLen(size)
            return len(obj)
        """
        mod = self.compile(src)
        assert mod.foo(5) == 5
        assert mod.foo(42) == 42
        assert mod.foo(0) == 0


    def test_len_not_supported(self):
        src = """
        def foo() -> None:
            return len(42)
        """
        errors = expect_errors(
            'cannot call len(`i32`)',
            ('this is `i32`', '42'),
        )
        self.compile_raises(src, "foo", errors)
