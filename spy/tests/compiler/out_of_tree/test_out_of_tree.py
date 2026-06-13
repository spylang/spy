import re

import py

from spy.errors import SPyError
from spy.tests.support import CompilerTest, only_interp, skip_backends
from spy.vm.vm import SPyVM

MYMOD_PATH = py.path.local(__file__).dirpath("mymod")


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
