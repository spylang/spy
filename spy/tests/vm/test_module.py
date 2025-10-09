from spy.fqn import FQN
from spy.vm.module import W_Module
from spy.vm.vm import SPyVM


class TestModule:
    def test_add(self):
        vm = SPyVM()
        w_mod = W_Module("mymod", "mymod.spy")
        vm.register_module(w_mod)
        w_a = vm.wrap(10)
        w_b = vm.wrap(20)
        w_mod.setattr("a", w_a)
        w_mod.setattr("b", w_b)
        assert list(w_mod.keys()) == ["a", "b"]
        assert list(w_mod.items_w()) == [
            ("a", w_a),
            ("b", w_b),
        ]
