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

@no_C
class TestOp(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def test_no_spy_new(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext')

        @EXT.builtin_type('MyClass')
        class W_MyClass(W_Object):
            pass
        # ========== /EXT module for this test =========

        self.vm.make_module(EXT)
        src = """
        from ext import MyClass

        def foo() -> MyClass:
            return MyClass()
        """
        errors = expect_errors(
            'cannot instantiate `ext::MyClass`',
            ('`ext::MyClass` does not have a method `__new__`', "MyClass"),
        )
        self.compile_raises(src, "foo", errors)

    def test_cannot_instante_red_class(self):
        src = """
        def bar(T: type) -> dynamic:
            return T()

        def foo() -> dynamic:
            return bar(i32)
        """
        errors = expect_errors(
            'instantiation of red types is not yet supported',
            ('this is red', "T"),
        )
        self.compile_raises(src, "foo", errors)


    def test_opimpl_type_mismatch(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext')

        @EXT.builtin_type('MyClass')
        class W_MyClass(W_Object):

            @builtin_method('__new__')
            @staticmethod
            def w_new(vm: 'SPyVM') -> 'W_MyClass':
                return W_MyClass()

            @builtin_method('__GETITEM__', color='blue')
            @staticmethod
            def w_GETITEM(vm: 'SPyVM', wop_obj: W_OpArg,
                          wop_i: W_OpArg) -> W_OpImpl:
                @builtin_func('ext')
                def w_getitem(vm: 'SPyVM', w_obj: W_MyClass,
                              w_i: W_I32) -> W_I32:
                    return w_i
                return W_OpImpl(w_getitem)
        # ========== /EXT module for this test =========

        self.vm.make_module(EXT)
        src = """
        from ext import MyClass

        def foo() -> i32:
            obj = MyClass()
            return obj['hello']
        """
        errors = expect_errors(
            'mismatched types',
            ('expected `i32`, got `str`', "'hello'"),
        )
        self.compile_raises(src, "foo", errors)

    def test_opimpl_wrong_argcount(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext')

        @EXT.builtin_type('MyClass')
        class W_MyClass(W_Object):

            @builtin_method('__new__')
            @staticmethod
            def w_new(vm: 'SPyVM') -> 'W_MyClass':
                return W_MyClass()

            @builtin_method('__GETITEM__', color='blue')
            @staticmethod
            def w_GETITEM(vm: 'SPyVM', wop_obj: W_OpArg,
                          wop_i: W_OpArg) -> W_OpImpl:
                @builtin_func('ext')
                def w_getitem(vm: 'SPyVM', w_obj: W_MyClass) -> W_I32:
                    return vm.wrap(42)  # type: ignore
                return W_OpImpl(w_getitem)
        # ========== /EXT module for this test =========

        self.vm.make_module(EXT)
        src = """
        from ext import MyClass

        def foo() -> i32:
            obj = MyClass()
            return obj[0]
        """
        errors = expect_errors(
            'this function takes 1 argument but 2 arguments were supplied',
        )
        self.compile_raises(src, "foo", errors)

    def test_complex_OpImpl(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext')

        @EXT.builtin_type('MyClass')
        class W_MyClass(W_Object):

            def __init__(self, w_x: W_I32):
                self.w_x = w_x

            @builtin_method('__new__')
            @staticmethod
            def w_new(vm: 'SPyVM', w_x: W_I32) -> 'W_MyClass':
                return W_MyClass(w_x)

            @builtin_method('__GETITEM__', color='blue')
            @staticmethod
            def w_GETITEM(vm: 'SPyVM', wop_obj: W_OpArg,
                          wop_i: W_OpArg) -> W_OpImpl:
                assert isinstance(wop_obj, W_OpArg)
                assert isinstance(wop_i, W_OpArg)
                # NOTE we are reversing the two arguments
                return W_OpImpl(EXT.w_sum, [wop_i, wop_obj])

        @EXT.builtin_func
        def w_sum(vm: 'SPyVM', w_i: W_I32, w_obj: W_MyClass) -> W_I32:
            assert isinstance(w_i, W_I32)
            assert isinstance(w_obj, W_MyClass)
            a = vm.unwrap_i32(w_i)
            b = vm.unwrap_i32(w_obj.w_x)
            return vm.wrap(a+b)  # type: ignore
        # ========== /EXT module for this test =========

        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import MyClass

        def foo(a: i32, b: i32) -> i32:
            obj = MyClass(a)
            return obj[b]
        """)
        assert mod.foo(10, 20) == 30

    def test_OpImpl_new(self):
        if self.backend == 'doppler':
            pytest.skip('OpImpl becomes blue? FIXME')

        mod = self.compile("""
        from operator import OpImpl

        def bar() -> void:
            pass

        def foo() -> dynamic:
            return OpImpl(bar)
        """)
        w_opimpl = mod.foo(unwrap=False)
        assert isinstance(w_opimpl, W_OpImpl)
        assert w_opimpl._w_func is mod.bar.w_func
