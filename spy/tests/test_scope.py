import textwrap
import pytest

from spy.parser import Parser
from spy.irgen.scope import ScopeAnalyzer
from spy.irgen.symtable import Symbol
from spy.vm.vm import SPyVM, Builtins as B
from spy.util import ANYTHING


@pytest.mark.usefixtures('init')
class TestScopeAnalyzer:

    @pytest.fixture
    def init(self, tmpdir):
        self.vm = SPyVM()
        self.tmpdir = tmpdir

    def analyze(self, src: str):
        f = self.tmpdir.join('test.spy')
        src = textwrap.dedent(src)
        f.write(src)
        parser = Parser(src, str(f))
        self.mod = parser.parse()
        scopes = ScopeAnalyzer(self.vm, self.mod)
        scopes.check_everything()
        return scopes

    ## def test_local_variables(self):
    ##     scopes = self.analyze("""
    ##     def foo() -> i32:
    ##         x: i32 = 42
    ##         return x
    ##     """)
    ##     funcdef = self.mod.get_funcdef('foo')
    ##     scope = scopes.by_funcdef(funcdef)
    ##     assert scope.symbols == {
    ##         'x': Symbol('x', 'var', B.w_i32, loc=ANYTHING, scope=scope),
    ##     }

    ## def test_function_arguments(self):
    ##     t = self.typecheck(
    ##     """
    ##     def inc(x: i32) -> i32:
    ##         return x + 1
    ##     """)
    ##     funcdef = self.mod.get_funcdef('inc')
    ##     w_expected_functype = W_FuncType.parse('def(x: i32) -> i32')
    ##     w_functype, scope = t.get_funcdef_info(funcdef)
    ##     assert w_functype == w_expected_functype
    ##     assert scope.symbols == {
    ##         '@return': Symbol('@return', 'var', B.w_i32, loc=ANYTHING,
    ##                           scope=scope),
    ##         'x': Symbol('x', 'var', B.w_i32, loc=ANYTHING, scope=scope),
    ##     }
