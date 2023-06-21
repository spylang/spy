from typing import Any
import textwrap
import pytest
from spy.vm.vm import SPyVM

@pytest.mark.usefixtures('init')
class CompilerTest:
    tmpdir: Any
    vm: SPyVM

    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir
        self.vm = SPyVM()

    def write_source(self, filename: str, src: str) -> Any:
        """
        Write the give source code to the specified filename, in the tmpdir.

        The source code is automatically dedented.
        """
        src = textwrap.dedent(src)
        srcfile = self.tmpdir.join(filename)
        srcfile.write(src)
        return srcfile
