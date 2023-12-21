import pytest
import textwrap
from spy import ast
from spy.parser import Parser
from spy.backend.spy import SPyBackend

@pytest.mark.usefixtures('init')
class TestSPyBackend:

    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir

    def parse(self, src: str) -> ast.Module:
        f = self.tmpdir.join('test.spy')
        src = textwrap.dedent(src)
        f.write(src)
        parser = Parser(src, str(f))
        self.mod = parser.parse()
        return self.mod

    def assert_dump(self, mod: ast.Module, expected: str) -> str:
        backend = SPyBackend(mod)
        got = backend.build().strip()
        expected = textwrap.dedent(expected).strip()
        assert got == expected

    def test_simple(self):
        mod = self.parse("""
        def foo() -> i32:
            pass
        """)
        self.assert_dump(mod, """
        def foo() -> i32:
            pass
        """)
