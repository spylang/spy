import pytest
from spy.parser import Parser
from spy.irgen.module import ModuleGen
from spy.vm.vm import SPyVM
from spy.errors import SPyTypeError

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

    def test_return_type_errors(self):
        with pytest.raises(SPyTypeError,
                           match='Only simple types are supported for now'):
            self.compile("""
            def foo() -> MyList[i32]:
                return 42
            """)
        with pytest.raises(SPyTypeError, match='Unknown type: aaa'):
            self.compile("""
            def foo() -> aaa:
                return 42
            """)
        #
        self.vm.builtins.w_I_am_not_a_type = self.vm.wrap(42)  # type: ignore
        with pytest.raises(SPyTypeError, match='I_am_not_a_type is not a type'):
            self.compile("""
            def foo() -> I_am_not_a_type:
                return 42
            """)
