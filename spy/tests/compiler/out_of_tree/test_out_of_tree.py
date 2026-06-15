import re
import subprocess

import py
import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, only_interp, skip_backends
from spy.vm.vm import SPyVM

MYMOD_PATH = py.path.local(__file__).dirpath("mymod")


@pytest.fixture(scope="module", autouse=True)
def build_mymod():
    archive = MYMOD_PATH.join("build", "wasi", "libmymod.a")
    sources = MYMOD_PATH.listdir("*.c") + MYMOD_PATH.listdir("*.h")
    if archive.exists() and all(archive.mtime() >= src.mtime() for src in sources):
        return
    subprocess.run(
        ["make", "TARGET=wasi"],
        cwd=str(MYMOD_PATH),
        check=True,
    )


class TestOutOfTree(CompilerTest):
    def test_simple(self):
        # override self.vm with our custom SPyVM
        self.vm = SPyVM(extra_vm_modules=[str(MYMOD_PATH)])
        self.vm.path.append(str(self.tmpdir))
        #
        mod = self.compile("""
        from mymod import get_name

        def foo() -> str:
            return get_name()
        """)
        assert mod.foo() == "hello from mymod"
