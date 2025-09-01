import pytest
from spy.vm.primitive import W_I32, W_Dynamic
from spy.vm.builtin import builtin_method
from spy.vm.w import W_Object
from spy.vm.opspec import W_OpSpec, W_MetaArg
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
    def w_LEN(vm: 'SPyVM', wm_self: W_MetaArg) -> W_OpSpec:
        @vm.register_builtin_func('ext')
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

    @no_C
    def test_builtin_func_dedup(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext')

        @EXT.builtin_func(color='blue')
        def w_make_func(vm: 'SPyVM', w_dummy: W_I32) -> W_Dynamic:
            fqn = EXT.fqn.join('make_func')

            @vm.register_builtin_func(fqn, 'impl')
            def w_impl(vm: 'SPyVM') -> W_I32:
                return vm.wrap(21)
            return w_impl

        # ========== /EXT module for this test =========

        self.vm.make_module(EXT)
        src = """
        from ext import make_func

        @blue
        def my_make_func(n):
            return make_func(n)

        def foo() -> i32:
            a = make_func(0)()
            b = make_func(1)()
            return a + b
        """
        mod = self.compile(src)

        # check that make_func(0) and make_func(1) return the SAME object
        if self.backend == 'interp':
            w_a = mod.my_make_func(0, unwrap=False)
            w_b = mod.my_make_func(1, unwrap=False)
            assert w_a is w_b

        # check that we can actually call them from SPy code
        assert mod.foo() == 42
