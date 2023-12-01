import pytest
import spy.ast
from spy.location import Loc
from spy.irgen.symtable import SymTable, SPyScopeError
from spy.vm.vm import SPyVM
from spy.vm.builtins import B

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
        sym = t.declare('a', 'red', LOC)
        assert sym.name == 'a'
        assert sym.color == 'red'
        assert sym.scope is t
        #
        assert t._lookup('a') is sym
        assert t._lookup('I-dont-exist') is None
        #
        with pytest.raises(SPyScopeError):
            t.declare('a', 'red', LOC)

    def test_nested_scope_lookup(self):
        glob = SymTable('<globals>', parent=None)
        loc = SymTable('loc', parent=glob)
        sym_a = glob.declare('a', 'red', LOC)
        sym_b = loc.declare('b', 'red', LOC)
        #
        assert glob._lookup('a') is sym_a
        assert glob._lookup('b') is None
        #
        assert loc._lookup('a') is sym_a
        assert loc._lookup('b') is sym_b

    def test_from_builtins(self):
        scope = SymTable.from_builtins(self.vm)
        sym = scope._lookup('i32')
        assert sym is not None
        assert sym.name == 'i32'
        assert sym.color == 'blue'
        #
        sym = scope._lookup('True')
        assert sym is not None
        assert sym.name == 'True'
