import subprocess
import py
from py.path import LocalPath

class ZigToolchain:

    def __init__(self) -> None:
        import ziglang  # type: ignore
        self.ZIG = py.path.local(ziglang.__file__).dirpath('zig')
        if not self.ZIG.check(exists=True):
            raise ValueError('Cannot find the zig executable; try pip install ziglang')

    def c2wasm(self, file_c: LocalPath, exports: list[str],
               file_wasm: LocalPath) -> LocalPath:
        """
        Compile the C code to WASM, using zig cc
        """
        cmdline = [
            str(self.ZIG), 'cc',
	    '--target=wasm32-freestanding',
	    '-nostdlib',
            '-shared',
	    '-g',
	    '-O3',
	    '-o', str(file_wasm),
	    str(file_c)
        ]
        for name in exports:
            cmdline.append(f'-Wl,--export={name}')
        #
        subprocess.check_call(cmdline)
        return file_wasm
