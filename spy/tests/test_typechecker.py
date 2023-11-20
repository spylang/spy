import textwrap
import pytest

from spy.parser import Parser
from spy.irgen.typechecker import TypeChecker
from spy.irgen.symtable import Symbol
from spy.vm.vm import SPyVM, Builtins as B
from spy.vm.function import W_FuncType
from spy.util import ANYTHING


@pytest.mark.usefixtures('init')
class TestTypechecker:

    @pytest.fixture
    def init(self, tmpdir):
        self.vm = SPyVM()
        self.tmpdir = tmpdir

    def typecheck(self, src: str):
        f = self.tmpdir.join('test.spy')
        src = textwrap.dedent(src)
        f.write(src)
        parser = Parser(src, str(f))
        self.mod = parser.parse()
        t = TypeChecker(self.vm, self.mod)
        t.check_everything(legacy=True)
        return t

    def test_simple(self):
        t = self.typecheck(
        """
        def foo() -> i32:
            return 42
        """)
        w_expected_functype = W_FuncType.parse('def() -> i32')
        assert t.global_scope.symbols == {
            'foo': Symbol('foo', 'const', w_expected_functype,
                          loc = ANYTHING,
                          scope = t.global_scope)
        }
        #
        funcdef = self.mod.get_funcdef('foo')
        w_expected_functype = W_FuncType([], B.w_i32)
        w_functype, scope = t.get_funcdef_info(funcdef)
        assert w_functype == w_expected_functype
        assert scope.symbols == {
            '@return': Symbol('@return', 'var', B.w_i32, loc=ANYTHING, scope=scope)
        }

    def test_local_variables(self):
        t = self.typecheck(
        """
        def foo() -> i32:
            x: i32 = 42
            return x
        """)
        # typechecker tests
        funcdef = self.mod.get_funcdef('foo')
        w_functype, scope = t.get_funcdef_info(funcdef)
        assert scope.symbols == {
            '@return': Symbol('@return', 'var', B.w_i32, loc=ANYTHING, scope=scope),
            'x': Symbol('x', 'var', B.w_i32, loc=ANYTHING, scope=scope),
        }

    def test_function_arguments(self):
        t = self.typecheck(
        """
        def inc(x: i32) -> i32:
            return x + 1
        """)
        funcdef = self.mod.get_funcdef('inc')
        w_expected_functype = W_FuncType.parse('def(x: i32) -> i32')
        w_functype, scope = t.get_funcdef_info(funcdef)
        assert w_functype == w_expected_functype
        assert scope.symbols == {
            '@return': Symbol('@return', 'var', B.w_i32, loc=ANYTHING,
                              scope=scope),
            'x': Symbol('x', 'var', B.w_i32, loc=ANYTHING, scope=scope),
        }
