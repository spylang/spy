import pytest
from spy.fqn import FQN
from spy.vm.b import B
from spy.vm.object import W_Type, W_Object, spytype
from spy.vm.str import W_Str
from spy.vm.registry import ModuleRegistry
from spy.tests.support import CompilerTest

class TestOperator(CompilerTest):

    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def test_getattr(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry('ext', '<ext>')

        @spytype('MyClass')
        class W_MyClass(W_Object):
            def getattr_impl(self, vm: 'SPyVM', w_attr: W_Str) -> W_Object:
                attr = vm.unwrap_str(w_attr)
                return vm.wrap(attr.upper() + '--42')

        EXT.add('MyClass', W_MyClass._w)

        @EXT.primitive('def() -> dynamic')
        def make(vm: 'SPyVM') -> W_Object:
            return W_MyClass()
        # ========== /EXT module for this test =========

        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import make, MyClass

        @blue
        def bar():
            x: MyClass = make()
            return x.hello

        def foo() -> str:
            return bar()
        """)

        res = mod.foo()
