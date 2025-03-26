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
