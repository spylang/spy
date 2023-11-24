import textwrap
import pytest

from spy.parser import Parser
from spy.irgen.scope import ScopeAnalyzer
from spy.irgen.symtable import Symbol, Color
from spy.vm.vm import SPyVM, Builtins as B

class MatchSymbol:
    """
    Helper class which compares equals to Symbol if the specified fields match
    """
    def __init__(self, name: str, color: Color):
        self.name = name
        self.color = color

    def __eq__(self, sym: Symbol) -> bool:
        if not isinstance(sym, Symbol):
            return NotImplemented
        return (self.name == sym.name and
                self.color == sym.color)


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
        scopes = ScopeAnalyzer(self.vm, 'test', self.mod)
        scopes.analyze()
        return scopes

    def test_global(self):
        scopes = self.analyze("""
        x: i32 = 0

        def foo() -> void:
            pass

        def bar() -> void:
            pass
        """)
        scope = scopes.by_module()
        assert scope.symbols == {
            'x': MatchSymbol('x', 'blue'),
            'foo': MatchSymbol('foo', 'blue'),
            'bar': MatchSymbol('bar', 'blue'),
        }

    def test_funcargs_and_locals(self):
        scopes = self.analyze("""
        def foo(x: i32) -> i32:
            y: i32 = 42
            z = 42
        """)
        funcdef = self.mod.get_funcdef('foo')
        scope = scopes.by_funcdef(funcdef)
        assert scope.name == 'foo'
        assert scope.parent == scopes.by_module()
        assert scope.symbols == {
            'x': MatchSymbol('x', 'red'),
            'y': MatchSymbol('y', 'red'),
            'z': MatchSymbol('z', 'red'),
        }
