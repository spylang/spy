import pytest
from spy.fqn import FQN
from spy.vm.vm import SPyVM
from spy.vm.b import B
from spy.vm.module import W_Module

class TestModule:

    def test_add(self):
        vm = SPyVM()
        w_mod = W_Module(vm, 'mymod', 'mymod.spy')
        vm.register_module(w_mod)
        #
        fqn_a = FQN('mymod::a')
        fqn_b = FQN('mymod::b')
        w_a = vm.wrap(10)
        w_b = vm.wrap(20)
        vm.add_global(fqn_a, B.w_i32, w_a)
        vm.add_global(fqn_b, B.w_i32, w_b)
        assert list(w_mod.keys()) == [fqn_a, fqn_b]
        assert list(w_mod.items_w()) == [
            (fqn_a, w_a),
            (fqn_b, w_b),
        ]
