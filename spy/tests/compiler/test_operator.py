import pytest
from spy.fqn import QN
from spy.vm.b import B
from spy.vm.object import spytype, Member, Annotated
from spy.vm.sig import spy_builtin
from spy.vm.w import W_Type, W_Object, W_Dynamic, W_Str, W_I32, W_Void
from spy.vm.opimpl import W_OpImpl
from spy.vm.registry import ModuleRegistry
from spy.vm.vm import SPyVM
from spy.tests.support import CompilerTest, no_C, expect_errors

@no_C
class TestOp(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def test_opimpl_type_mismatch(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext', '<ext>')

        @EXT.spytype('MyClass')
        class W_MyClass(W_Object):

            @staticmethod
            def spy_new(vm: 'SPyVM', w_cls: W_Type) -> 'W_MyClass':
                return W_MyClass()

            @staticmethod
            def op_GETITEM(vm: 'SPyVM', w_listtype: W_Type,
                           w_itype: W_Type) -> W_OpImpl:
                @spy_builtin(QN('ext::getitem'))
                def getitem(vm: 'SPyVM', w_obj: W_MyClass, w_i: W_I32) -> W_I32:
                    return w_i
                return W_OpImpl(vm.wrap_func(getitem))
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
        EXT = ModuleRegistry('ext', '<ext>')

        @EXT.spytype('MyClass')
        class W_MyClass(W_Object):

            @staticmethod
            def spy_new(vm: 'SPyVM', w_cls: W_Type) -> 'W_MyClass':
                return W_MyClass()

            @staticmethod
            def op_GETITEM(vm: 'SPyVM', w_listtype: W_Type,
                           w_itype: W_Type) -> W_OpImpl:
                @spy_builtin(QN('ext::getitem'))
                def getitem(vm: 'SPyVM', w_obj: W_MyClass) -> W_Void:
                    return B.w_None
                return W_OpImpl(vm.wrap_func(getitem))
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
