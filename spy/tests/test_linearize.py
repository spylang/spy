import textwrap

import pytest

from spy.backend.spy import FQN_FORMAT, SPyBackend
from spy.linearize import linearize
from spy.util import print_diff
from spy.vm.function import W_ASTFunc
from spy.vm.vm import SPyVM


@pytest.mark.usefixtures("init")
class TestLinearize:
    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir
        self.vm = SPyVM()
        self.vm.path.append(str(self.tmpdir))

    def import_src(self, src: str) -> None:
        f = self.tmpdir.join("test.spy")
        src = textwrap.dedent(src)
        f.write(src)
        self.vm.import_("test")

    def linearize(self, src: str) -> None:
        self.import_src(src)
        self.vm.redshift(error_mode="eager")
        for fqn, w_func in list(self.vm.fqns_by_modname("test")):
            if isinstance(w_func, W_ASTFunc) and w_func.redshifted:
                w_newfunc = linearize(self.vm, w_func)
                w_func.invalidate(w_newfunc)
                self.vm.globals_w[fqn] = w_newfunc

    def assert_dump(self, expected: str, *, fqn_format: FQN_FORMAT = "short") -> None:
        b = SPyBackend(self.vm, fqn_format=fqn_format)
        got = b.dump_mod("test").strip()
        expected = textwrap.dedent(expected).strip()
        if got != expected:
            print_diff(expected, got, "expected", "got")
            pytest.fail("assert_dump failed")

    def test_simple(self):
        src = """
        def foo(x: i32) -> i32:
            return x
        """
        self.linearize(src)
        self.assert_dump(src)
