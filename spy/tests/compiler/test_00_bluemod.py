from typing import Any, Literal, Optional
import textwrap
import pytest
from spy.vm.vm import SPyVM

@pytest.mark.usefixtures('init')
class TestBlueMod:

    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir
        self.vm = SPyVM()
        self.vm.path.append(str(tmpdir))

    def write_file(self, filename: str, src: str) -> Any:
        """
        Write the give source code to the specified filename, in the tmpdir.

        The source code is automatically dedented.
        """
        src = textwrap.dedent(src)
        srcfile = self.tmpdir.join(filename)
        srcfile.write(src)
        return srcfile

    def test_simple(self):
        self.write_file("test.spy", """
        @blue
        def foo():
            return 42
        """)
        w_mod = self.vm.import_("test")
        w_foo = w_mod.getattr("foo")
        w_res = self.vm.call_function(w_foo, [])
