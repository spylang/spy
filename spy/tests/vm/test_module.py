import pytest
from spy.vm.vm import SPyVM, Builtins as B
from spy.vm.module import W_Module

class TestModule:

    def test_add(self):
        vm = SPyVM()
        w_mod = W_Module(vm, 'mymod')
        w_a = vm.wrap(10)
        w_b = vm.wrap(20)
        w_mod.add('a', w_a)
        w_mod.add('b', w_b)
        assert w_mod.content.types_w == {
            'a': B.w_i32,
            'b': B.w_i32,
        }
        assert w_mod.content.values_w == {
            'a': w_a,
            'b': w_b,
        }

    def test_freeze(self):
        vm = SPyVM()
        w_mod = W_Module(vm, 'mymod')
        w_a = vm.wrap(10)
        w_b = vm.wrap(20)
        w_mod.add('a', w_a)
        w_mod.freeze()
        with pytest.raises(Exception, match='Frozen'):
            w_mod.add('b', w_b)
        assert list(w_mod.content.values_w.keys()) == ['a']
