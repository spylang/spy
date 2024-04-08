import pytest
from spy.fqn import FQN
from spy.vm.b import B
from spy.vm.object import spytype, Member, Annotated
from spy.vm.function import spy_builtin
from spy.vm.w import W_Type, W_Object, W_Dynamic, W_Str, W_I32, W_Void
from spy.vm.registry import ModuleRegistry
from spy.vm.vm import SPyVM
from spy.tests.support import CompilerTest, no_C

@no_C
class TestAttrOp(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def test_member(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext', '<ext>')

        @spytype('MyClass')
        class W_MyClass(W_Object):
            w_x: Annotated[W_I32, Member('x')]

            def __init__(self) -> None:
                self.w_x = W_I32(0)

        EXT.add('MyClass', W_MyClass._w)

        @EXT.builtin
        def make(vm: 'SPyVM') -> W_MyClass:
            return W_MyClass()
        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import make, MyClass

        @blue
        def foo():
            obj: MyClass = make()
            obj.x = 123
            return obj.x
        """)
        x = mod.foo()
        assert x == 123


    def test_getattr_setattr_custom(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext', '<ext>')

        @spytype('MyClass')
        class W_MyClass(W_Object):

            def __init__(self) -> None:
                self.x = 0

            @staticmethod
            def op_GETATTR(vm: 'SPyVM', w_type: W_Type,
                           w_attr: W_Str) -> W_Dynamic:
                attr = vm.unwrap_str(w_attr)
                if attr == 'x':
                    @spy_builtin(FQN('ext::getx'))
                    def opimpl(vm: 'SPyVM', w_obj: W_MyClass,
                                    w_attr: W_Str) -> W_I32:
                        return vm.wrap(w_obj.x)  # type: ignore
                else:
                    @spy_builtin(FQN('ext::getany'))
                    def opimpl(vm: 'SPyVM', w_obj: W_MyClass,
                                      w_attr: W_Str) -> W_Str:
                        attr = vm.unwrap_str(w_attr)
                        return vm.wrap(attr.upper() + '--42')  # type: ignore
                return vm.wrap(opimpl)

            @staticmethod
            def op_SETATTR(vm: 'SPyVM', w_type: W_Type, w_attr: W_Str,
                           w_vtype: W_Type) -> W_Dynamic:
                attr = vm.unwrap_str(w_attr)
                if attr == 'x':
                    @spy_builtin(FQN('ext::setx'))
                    def opimpl(vm: 'SPyVM', w_obj: W_MyClass,
                               w_attr: W_Str, w_val: W_I32) -> W_Void:
                        w_obj.x = vm.unwrap_i32(w_val)
                        return B.w_None
                    return vm.wrap(opimpl)
                else:
                    return B.w_NotImplemented


        EXT.add('MyClass', W_MyClass._w)

        @EXT.builtin
        def make(vm: 'SPyVM') -> W_MyClass:
            return W_MyClass()  # type: ignore
        # ========== /EXT module for this test =========

        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import make, MyClass

        @blue
        def get_hello():
            obj: MyClass = make()
            return obj.hello

        @blue
        def get_x():
            obj: MyClass = make()
            return obj.x

        @blue
        def set_get_x():
            obj: MyClass = make()
            obj.x = 123
            return obj.x
        """)
        assert mod.get_hello() == 'HELLO--42'
        assert mod.get_x() == 0
        assert mod.set_get_x() == 123
