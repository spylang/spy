from typing import Any
import textwrap
import pytest
from spy import interop

@pytest.mark.usefixtures('init')
class TestInterop:
    tmpdir: Any

    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir
        self.foo_spy = tmpdir.join('foo.spy')
        self.foo_spy.write(textwrap.dedent("""
        def add(x: i32, y: i32) -> i32:
            return x + y
        """))

    def test_redshift(self):
        vm, w_mod = interop.redshift(str(self.foo_spy))
        assert w_mod.name == 'foo'
        w_add = w_mod.getattr('add')
        assert repr(w_add) == "<spy function 'foo::add' (redshifted)>"

    def test_main(self):
        # here we just check that main() doesn't crash
        argv = ['interop.py', str(self.foo_spy)]
        interop.main(argv)
