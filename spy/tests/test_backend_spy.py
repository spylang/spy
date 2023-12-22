import pytest
import textwrap
from spy import ast
from spy.parser import Parser
from spy.backend.spy import dump_module
from spy.util import print_diff
from spy.tests.support import parse

@pytest.mark.usefixtures('init')
class TestSPyBackend:

    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir

    def parse(self, src: str) -> ast.Module:
        return parse(src, self.tmpdir)

    def assert_dump(self, mod: ast.Module, expected: str) -> None:
        got = dump_module(mod).strip()
        expected = textwrap.dedent(expected).strip()
        if got != expected:
            print_diff(expected, got, 'expected', 'got')
            pytest.fail('assert_dump failed')

    def test_simple(self):
        mod = self.parse("""
        def foo() -> i32:
            pass
        """)
        self.assert_dump(mod, """
        def foo() -> i32:
            pass
        """)

    def test_args_and_return(self):
        mod = self.parse("""
        def foo(x: i32, y: i32) -> i32:
            return 42
        """)
        self.assert_dump(mod, """
        def foo(x: i32, y: i32) -> i32:
            return 42
        """)

    def test_expr_precedence(self):
        mod = self.parse("""
        def foo() -> void:
            a = 1 + 2 * 3
            b = 1 + (2 * 3)
            c = (1 + 2) * 3
        """)
        self.assert_dump(mod, """
        def foo() -> void:
            a = 1 + 2 * 3
            b = 1 + 2 * 3
            c = (1 + 2) * 3
        """)

    def test_vardef(self):
        src = """
        def foo() -> void:
            x: i32 = 1
        """
        mod = self.parse(src)
        self.assert_dump(mod, src)
