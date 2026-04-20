import textwrap

import pytest

from spy.backend.spy import FQN_FORMAT, SPyBackend
from spy.linearize import linearize as linearize
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

    def assert_dump(self, expected: str, *, fqn_format: FQN_FORMAT = "short") -> None:
        funcs = [
            (fqn, w_func)
            for fqn, w_func in self.vm.fqns_by_modname("test")
            if isinstance(w_func, W_ASTFunc) and w_func.redshifted
        ]
        parts = []
        for fqn, w_func in funcs:
            result = linearize(w_func)
            assert w_func.locals_types_w is not None
            new_locals_types_w = dict(w_func.locals_types_w)
            new_locals_types_w.update(result.extra_locals)
            w_linearized = W_ASTFunc(
                fqn=w_func.fqn,
                closure=w_func.closure,
                w_functype=w_func.w_functype,
                funcdef=result.funcdef,
                defaults_w=w_func.defaults_w,
                locals_types_w=new_locals_types_w,
            )
            b = SPyBackend(self.vm, fqn_format=fqn_format)
            b.modname = "test"
            b.dump_w_func(fqn, w_linearized)
            parts.append(b.out.build().strip())
        got = "\n\n".join(parts)
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

    def test_blockexpr_simple(self):
        src = """
        def foo(a: i32) -> i32:
            return __block__('''
                x: i32 = a
                x
            ''')
        """
        self.linearize(src)
        self.assert_dump("""
        def foo(a: i32) -> i32:
            x: i32 = a
            return x
        """)
