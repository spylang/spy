import pytest
import spy.ast
from spy.location import Loc
from spy.irgen.symtable import SymTable, SymbolAlreadyDeclaredError
from spy.vm.vm import SPyVM, Builtins as B

LOC = Loc('<fake loc>', 0, 0, 0, 0)

@pytest.mark.usefixtures('init')
class TestSymtable:

    @pytest.fixture
    def init(self):
        self.vm = SPyVM()
        self.w_1 = self.vm.wrap(1)
        self.w_2 = self.vm.wrap(2)

    def test_basic(self):
        t = SymTable('<globals>', parent=None)
        sym = t.declare('a', 'var', LOC)
        assert sym.name == 'a'
        assert sym.qualifier == 'var'
        assert sym.scope is t
        #
        assert t.lookup('a') is sym
        assert t.lookup('I-dont-exist') is None
        #
        with pytest.raises(SymbolAlreadyDeclaredError):
            t.declare('a', 'var', LOC)

    def test_nested_scope_lookup(self):
        glob = SymTable('<globals>', parent=None)
        loc = SymTable('loc', parent=glob)
        sym_a = glob.declare('a', 'var', LOC)
        sym_b = loc.declare('b', 'const', LOC)
        #
        assert glob.lookup('a') is sym_a
        assert glob.lookup('b') is None
        #
        assert loc.lookup('a') is sym_a
        assert loc.lookup('b') is sym_b

    def test_from_builtins(self):
        scope = SymTable.from_builtins(self.vm)
        sym = scope.lookup('i32')
        assert sym is not None
        assert sym.name == 'i32'
        assert sym.qualifier == 'const'
        #
        sym = scope.lookup('True')
        assert sym is not None
        assert sym.name == 'True'
