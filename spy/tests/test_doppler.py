import textwrap
import pytest
from spy import ast
from spy.vm.vm import SPyVM
from spy.doppler import redshift
from spy.backend.spy import dump_module
from spy.util import print_diff
from spy.tests.support import parse

@pytest.mark.usefixtures('init')
class TestDoppler:

    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir
        self.vm = SPyVM()

    def redshift(self, src: str) -> ast.Module:
        mod = parse(src, self.tmpdir)
        newmod = redshift(self.vm, mod)
        return newmod

    def assert_dump(self, mod: ast.Module, expected: str) -> None:
        got = dump_module(mod).strip()
        expected = textwrap.dedent(expected).strip()
        if got != expected:
            print_diff(expected, got, 'expected', 'got')
            pytest.fail('assert_dump failed')

    @pytest.mark.xfail
    def test_simple(self):
        mod = self.redshift("""
        def foo() -> i32:
            return 1 + 2
        """)
        self.assert_dump(mod, """
        def foo() -> i32:
            return 3
        """)
