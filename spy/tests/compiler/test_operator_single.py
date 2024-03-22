import pytest
from spy.fqn import FQN
from spy.vm.b import B
from spy.vm.object import W_Type, W_Object, spytype
from spy.vm.str import W_Str
from spy.vm.registry import ModuleRegistry
from spy.vm.vm import SPyVM
from spy.tests.support import CompilerTest, no_C

@no_C
class TestOperatorSingle(CompilerTest):

    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def test_getattr_setattr_custom(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext', '<ext>')

        @spytype('MyClass')
        class W_MyClass(W_Object):

            def __init__(self):
                self.x = 0

            def getattr_impl(self, vm: 'SPyVM', w_attr: W_Str) -> W_Object:
                attr = vm.unwrap_str(w_attr)
                if attr == 'x':
                    return vm.wrap(self.x)
                return vm.wrap(attr.upper() + '--42')

            def setattr_impl(self, vm: 'SPyVM', w_attr: 'W_Str',
                             w_val: 'W_Object') -> None:
                attr = vm.unwrap_str(w_attr)
                if attr == 'x':
                    self.x = vm.unwrap_i32(w_val)
                else:
                    raise NotImplementedError

        EXT.add('MyClass', W_MyClass._w)

        @EXT.primitive('def() -> dynamic')
        def make(vm: 'SPyVM') -> W_Object:
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
