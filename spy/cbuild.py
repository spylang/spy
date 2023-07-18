from typing import Optional
import subprocess
import py.path
import spy

INCLUDE = spy.ROOT.join('libspy', 'include')
LIBSPY_A = spy.ROOT.join('libspy', 'libspy.a')

class ZigToolchain:

    def __init__(self) -> None:
        import ziglang  # type: ignore
        self.ZIG = py.path.local(ziglang.__file__).dirpath('zig')
        if not self.ZIG.check(exists=True):
            raise ValueError('Cannot find the zig executable; try pip install ziglang')

    def c2wasm(self, file_c: py.path.local, file_wasm: py.path.local,
               *, exports: Optional[list[str]] = None) -> py.path.local:
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
        #
        # for multivalue support
        cmdline += [
            '-mmultivalue',
            '-Xclang', '-target-abi',
            '-Xclang', 'experimental-mv'
        ]
        # make sure that libspy is available
        cmdline += [
            '-I', str(INCLUDE),
            str(LIBSPY_A),
        ]
        #
        if exports:
            for name in exports:
                cmdline.append(f'-Wl,--export={name}')
        #
        subprocess.check_call(cmdline)
        return file_wasm
