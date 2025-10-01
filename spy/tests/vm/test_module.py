from spy.fqn import FQN
from spy.vm.vm import SPyVM
from spy.vm.module import W_Module

class TestModule:

    def test_add(self):
        vm = SPyVM()
        w_mod = W_Module('mymod', 'mymod.spy')
        vm.register_module(w_mod)
        #
        fqn_a = FQN('mymod::a')
        fqn_b = FQN('mymod::b')
        w_a = vm.wrap(10)
        w_b = vm.wrap(20)
        w_mod.setattr("a", w_a)
        w_mod.setattr("b", w_b)
        assert list(w_mod.keys()) == ["a", "b"]
        assert list(w_mod.items_w()) == [
            ("a", w_a),
            ("b", w_b),
        ]
