import subprocess
from pathlib import Path

from spy.vm.vm import SPyVM


class ExeWrapper:
    def __init__(self, vm: SPyVM, modname: str, f: Path) -> None:
        # vm and modname are ignored
        self.f = f

    def run(self, *args: str) -> str:
        if self.f.suffix == ".mjs":
            # run with node
            cmdline = ["node", str(self.f)]
            cmdline += list(args)
            out = subprocess.check_output(cmdline)
            return out.decode("utf-8")
        else:
            raise NotImplementedError
