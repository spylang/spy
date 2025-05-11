from typing import Any
import subprocess
import py.path

from spy.vm.vm import SPyVM

class ExeWrapper:

    def __init__(self, vm: SPyVM, modname: str, f: py.path.local) -> None:
        # vm and modname are ignored
        self.f = f

    def run(self, *args: str) -> str:
        if self.f.ext == '.mjs':
            # run with node
            out = subprocess.check_output(['node', self.f] + list(args))
            return out.decode('utf-8')
        else:
            raise NotImplementedError
