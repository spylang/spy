from typing import Optional
import subprocess
import py.path
import spy.libspy

def get_toolchain(toolchain: str) -> 'Toolchain':
    if toolchain == 'zig':
        return ZigToolchain()
    elif toolchain == 'clang':
        return ClangToolchain()
    elif toolchain == 'emscripten':
        return EmscriptenToolchain()
    elif toolchain == 'native':
        return NativeToolchain()


class Toolchain:

    TARGET = '' # 'wasm', 'native', 'emscripten'

    @property
    def CC(self):
        raise NotImplementedError

    @property
    def CFLAGS(self):
        libspy_a = spy.libspy.BUILD.join(self.TARGET, 'libspy.a')
        return [
            '-O3',
            '--std=c99',
            '-Werror=implicit-function-declaration',
            #'-Werror',
            '-I', str(spy.libspy.INCLUDE),
            str(libspy_a),
        ]

    @property
    def WASM_CFLAGS(self):
        return [
            '-mmultivalue',
            '-Xclang', '-target-abi',
            '-Xclang', 'experimental-mv'
        ]

    def c2wasm(self, file_c: py.path.local, file_wasm: py.path.local, *,
               exports: Optional[list[str]] = None,
               debug_symbols: bool = False,
               ) -> py.path.local:
        """
        Compile the C code to WASM, using zig cc
        """
        cmdline = self.CC + self.CFLAGS + self.WASM_CFLAGS
        cmdline += [
	    '-o', str(file_wasm),
	    str(file_c)
        ]
        if debug_symbols:
            cmdline += ['-g', '-O0']
        if exports:
            for name in exports:
                cmdline.append(f'-Wl,--export={name}')
        #
        subprocess.check_call(cmdline)
        return file_wasm

    def c2exe(self, file_c: py.path.local, file_exe: py.path.local, *,
              debug_symbols: bool = False,
               ) -> py.path.local:
        cmdline = self.CC + self.CFLAGS
        cmdline += [
	    '-o', str(file_exe),
	    str(file_c)
        ]
        if debug_symbols:
            cmdline += ['-g', '-O0']

        cmdline += [
            spy.ROOT.join('libspy', 'src', 'emcompat.c'), # XXX
        ]
        #
        subprocess.check_call(cmdline)
        return file_exe



class ZigToolchain(Toolchain):

    TARGET = 'wasm32'

    def __init__(self) -> None:
        import ziglang  # type: ignore
        self.ZIG = py.path.local(ziglang.__file__).dirpath('zig')
        if not self.ZIG.check(exists=True):
            raise ValueError('Cannot find the zig executable; try pip install ziglang')

    @property
    def CC(self):
        return [str(self.ZIG), 'cc']

    @property
    def WASM_CFLAGS(self):
        return super().WASM_CFLAGS + [
	    '--target=wasm32-freestanding',
	    '-nostdlib',
            '-shared',
        ]


class ClangToolchain(Toolchain):

    TARGET = 'wasm32'

    @property
    def CC(self):
        return ['clang']

    @property
    def WASM_CFLAGS(self):
        return super().WASM_CFLAGS + [
	    '--target=wasm32',
	    '-nostdlib',
            '-Wl,--no-entry',
        ]


class NativeToolchain(Toolchain):

    TARGET = 'native'
    EXE_FILENAME_EXT = ''

    @property
    def CC(self):
        return ['cc']


class EmscriptenToolchain:

    def __init__(self) -> None:
        self.EMCC = py.path.local.sysfind('emcc')
        if self.EMCC is None:
            raise ValueError('Cannot find the emcc executable')

    # XXX this should be renamed?
    def c2wasm(self, file_c: py.path.local, file_wasm: py.path.local, *,
               exports: Optional[list[str]] = None,
               debug_symbols: bool = False,
               ) -> py.path.local:

        file_js = file_wasm.new(ext='.js')

        cmdline = [
            self.EMCC,
            '--std=c99',
            '-Werror=implicit-function-declaration',
	    '-o', str(file_js),
	    str(file_c)
        ]
        if debug_symbols:
            cmdline += ['-g', '-O0']
        else:
            cmdline += ['-O3']
        #
        # for multivalue support
        cmdline += [
            '-mmultivalue',
            '-Xclang', '-target-abi',
            '-Xclang', 'experimental-mv'
        ]
        # make sure that libspy is available

        # hack hack hack
        # XXX fix this before merging the PR!
        LIBSPY = spy.libspy.LIBSPY_A.join('..', '..', '..')
        LIBSPY_A = LIBSPY.join('build', 'emscripten', 'libspy.a')
        cmdline += [
            '-I', str(spy.libspy.INCLUDE),
            LIBSPY_A,
            LIBSPY.join('src', 'emcompat.c'),
        ]
        #
        if exports:
            # TODO
            pass

        cmdline += [
            "-sEXPORTED_FUNCTIONS=['_main']",
            "-sDEFAULT_LIBRARY_FUNCS_TO_INCLUDE='$dynCall'"
        ]
        #
        subprocess.check_call(cmdline)
        return file_js
