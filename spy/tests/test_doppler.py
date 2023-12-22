import textwrap
import pytest
from spy import ast
from spy.vm.vm import SPyVM
from spy.vm.function import W_ASTFunc
from spy.doppler import redshift
from spy.backend.spy import dump_function
from spy.util import print_diff

@pytest.mark.usefixtures('init')
class TestDoppler:

    @pytest.fixture
    def init(self, tmpdir):
        # XXX there is a lot of code duplication with CompilerTest
        self.tmpdir = tmpdir
        self.vm = SPyVM()
        self.vm.path.append(str(self.tmpdir))

    def redshift(self, src: str, funcname: str) -> W_ASTFunc:
        f = self.tmpdir.join('test.spy')
        src = textwrap.dedent(src)
        f.write(src)
        w_mod = self.vm.import_('test')
        w_func = w_mod.getattr(funcname)
        return redshift(self.vm, w_func)

    def assert_dump(self, w_func: W_ASTFunc, expected: str) -> None:
        got = dump_function(w_func).strip()
        expected = textwrap.dedent(expected).strip()
        if got != expected:
            print_diff(expected, got, 'expected', 'got')
            pytest.fail('assert_dump failed')

    def test_simple(self):
        src = """
        def foo() -> i32:
            return 1 + 2
        """
        w_func = self.redshift(src, 'foo')
        self.assert_dump(w_func, """
        def foo() -> i32:
            return 3
        """)

    def test_red_vars(self):
        src = """
        def foo() -> i32:
            x: i32 = 1
            return x
        """
        w_func = self.redshift(src, 'foo')
        self.assert_dump(w_func, src)

    def test_funcargs(self):
        src = """
        def foo(x: i32, y: i32) -> i32:
            return x + y
        """
        w_func = self.redshift(src, 'foo')
        self.assert_dump(w_func, src)
