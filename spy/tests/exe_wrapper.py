import subprocess

import py.path

from spy.vm.vm import SPyVM


class ExeWrapper:
    def __init__(self, vm: SPyVM, modname: str, f: py.path.local) -> None:
        # vm and modname are ignored
        self.f = f

    def run(self, *args: str) -> str:
        if self.f.ext == ".mjs":
            cmdline = ["node"]  # run with node
        else:
            cmdline = []
        cmdline += [str(self.f)]
        cmdline += list(args)
        out = subprocess.check_output(cmdline)
        return out.decode("utf-8")
