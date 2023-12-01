import textwrap
import pytest
from spy import ast
from spy.ast_dump import dump
from spy.parser import Parser
from spy.irgen.scope import ScopeAnalyzer
from spy.irgen.symtable import Symbol, Color
from spy.vm.vm import SPyVM
from spy.vm.builtins import B
from spy.tests.support import expect_errors, MatchAnnotation

class MatchSymbol:
    """
    Helper class which compares equals to Symbol if the specified fields match
    """
    def __init__(self, name: str, color: Color):
        self.name = name
        self.color = color

    def __eq__(self, sym: object) -> bool:
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

    def expect_errors(self, src: str, main: str, *anns: MatchAnnotation):
        with expect_errors(main, *anns):
            self.analyze(src)

    def assert_dump(self, node: ast.Node, expected: str):
        dumped = dump(node, use_colors=False)
        expected = textwrap.dedent(expected)
        if '{tmpdir}' in expected:
            expected = expected.format(tmpdir=self.tmpdir)
        assert dumped.strip() == expected.strip()

    def test_global(self):
        scopes = self.analyze("""
        x: i32 = 0

        def foo() -> void:
            pass

        def bar() -> void:
            pass
        """)
        scope = scopes.by_module()
        assert scope._symbols == {
            'x': MatchSymbol('x', 'blue'),
            'foo': MatchSymbol('foo', 'blue'),
            'bar': MatchSymbol('bar', 'blue'),
            # captured
            'i32': MatchSymbol('i32', 'blue'),
            'void': MatchSymbol('void', 'blue'),
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
        assert scope._symbols == {
            'x': MatchSymbol('x', 'red'),
            'y': MatchSymbol('y', 'red'),
            'z': MatchSymbol('z', 'red'),
            # captured
            'i32': MatchSymbol('i32', 'blue'),
        }
        assert funcdef.symtable is scope

    def test_assign_does_not_redeclare(self):
        scopes = self.analyze("""
        def foo() -> void:
            x: i32 = 0
            x = 1
        """)
        funcdef = self.mod.get_funcdef('foo')
        scope = scopes.by_funcdef(funcdef)
        assert scope._symbols == {
            'x': MatchSymbol('x', 'red'),
            'i32': MatchSymbol('i32', 'blue'),
        }

    def test_cannot_redeclare(self):
        src = """
        def foo() -> i32:
            x: i32 = 1
            x: i32 = 2
        """
        self.expect_errors(
            src,
            'variable `x` already declared',
            ('this is the new declaration', "x: i32 = 2"),
            ('this is the previous declaration', "x: i32 = 1"),
        )

    def test_no_shadowing(self):
        src = """
        x: i32 = 1
        def foo() -> i32:
            x: i32 = 2
        """
        self.expect_errors(
            src,
            'variable `x` shadows a name declared in an outer scope',
            ('this is the new declaration', "x: i32 = 2"),
            ('this is the previous declaration', "x: i32 = 1"),
        )

    def test_inner_funcdef(self):
        self.analyze("""
        def foo() -> void:
            x: i32 = 0
            def bar(y: i32) -> i32:
                return x + y
        """)
        foodef = self.mod.get_funcdef('foo')
        assert foodef.symtable._symbols == {
            'x': MatchSymbol('x', 'red'),
            'bar': MatchSymbol('bar', 'blue'),
            'i32': MatchSymbol('i32', 'blue'),
        }
        #
        bardef = foodef.body[1]
        assert isinstance(bardef, ast.FuncDef)
        assert bardef.symtable._symbols == {
            'y': MatchSymbol('y', 'red'),
            'x': MatchSymbol('x', 'red'),
        }
