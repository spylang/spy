from spy.fqn import FQN
from spy.tests.support import CompilerTest, expect_errors, no_C, only_interp
from spy.vm.b import B
from spy.vm.object import W_Type


class TestDict(CompilerTest):
    @no_C
    def test_empty_dict_singleton(self):
        src = """
        import __spy__

        def get_empty() -> __spy__.EmptyDictType:
            return {}
        """
        mod = self.compile(src)
        w_a = mod.get_empty(unwrap=False)
        w_b = mod.get_empty(unwrap=False)
        assert w_a is w_b
