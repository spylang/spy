import pytest
from spy.parser import Parser
from spy.irgen.module import ModuleGen
from spy.vm.vm import SPyVM

@pytest.mark.usefixtures('init')
class TestIRGen:

    @pytest.fixture
    def init(self):
        self.vm = SPyVM()

    def compile(self, src: str):
        p = Parser.from_string(src, dedent=True)
        mod = p.parse()
        modgen = ModuleGen(self.vm, mod)
        return modgen.make_w_mod()

    def test_simple(self):
        w_mod = self.compile("""
        def foo() -> i32:
            return 42
        """)
        vm = self.vm
        w_foo = w_mod.content.get('foo')
        w_result = vm.call_function(w_foo, [])
        assert vm.unwrap(w_result) == 42
