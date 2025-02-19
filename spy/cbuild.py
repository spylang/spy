from typing import Optional, Literal
import subprocess
import py.path
import spy.libspy
from spy.textbuilder import Color

FORCE_COLORS=True
BUILD_TYPE = Literal['release', 'debug']

def get_toolchain(toolchain: str, *, build_type: BUILD_TYPE) -> 'Toolchain':
    if toolchain == 'zig':
        return ZigToolchain(build_type)
    elif toolchain == 'clang':
        return ClangToolchain(build_type)
    elif toolchain == 'emscripten':
        return EmscriptenToolchain(build_type)
    elif toolchain == 'native':
        return NativeToolchain(build_type)
    else:
        raise ValueError(f"Unknown toolchain: {toolchain}")


class Toolchain:

    TARGET = '' # 'wasi', 'native', 'emscripten'
    EXE_FILENAME_EXT = ''

    def __init__(self, build_type: BUILD_TYPE) -> None:
        self.build_type = build_type

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        return f'<{cls} for {self.TARGET} ({self.build_type})>'

    @property
    def CC(self) -> list[str]:
        raise NotImplementedError

    @property
    def CFLAGS(self) -> list[str]:
        libspy_a = spy.libspy.BUILD.join(self.TARGET, 'libspy.a')
        return [
            '-DSPY_TARGET_' + self.TARGET.upper(),
            '--std=c99',
            '-Werror=implicit-function-declaration',
            '-Wfatal-errors',
            #'-Werror',
            '-I', str(spy.libspy.INCLUDE),
        ]

    @property
    def WASM_CFLAGS(self) -> list[str]:
        return [
            '-mmultivalue',
            '-Xclang', '-target-abi',
            '-Xclang', 'experimental-mv'
        ]

    @property
    def LDFLAGS(self) -> list[str]:
        libspy_dir = spy.libspy.BUILD.join(self.TARGET, self.build_type)
        return ['-L', str(libspy_dir), '-lspy']

    def cc(self,
           file_c: py.path.local,
           file_out: py.path.local,
           *,
           opt_level: int,
           debug_symbols: bool,
           EXTRA_CFLAGS: Optional[list[str]] = None,
           EXTRA_LDFLAGS: Optional[list[str]] = None,
           ) -> py.path.local:
        EXTRA_CFLAGS = EXTRA_CFLAGS or []
        EXTRA_LDFLAGS = EXTRA_LDFLAGS or []
        cmdline = self.CC + self.CFLAGS + EXTRA_CFLAGS
        cmdline += [f'-O{opt_level}']
        if debug_symbols:
            cmdline += ['-g']

        if self.build_type == 'release':
            cmdline += ['-DSPY_RELEASE']
        elif self.build_type == 'debug':
            cmdline += ['-DSPY_DEBUG']
        else:
            assert False
        file_out = file_out.new(ext='.mjs')
        cmdline += [
            '-o', str(file_out),
            str(file_c)
        ]
        cmdline += self.LDFLAGS + EXTRA_LDFLAGS
        if FORCE_COLORS:
            cmdline = ['unbuffer'] + cmdline
        print(" ".join(cmdline))
        proc = subprocess.run(cmdline,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT)
        if proc.returncode != 0:
            lines = ["Compilation failed!"]
            lines.append(' '.join(cmdline))
            lines.append('')
            errlines = proc.stdout.decode('utf-8').splitlines()
            if FORCE_COLORS:
                errlines = [Color.set('default', line) for line in errlines]
            lines += errlines
            msg = '\n'.join(lines)
            raise Exception(msg)
        return file_out


    def c2wasm(self, file_c: py.path.local, file_wasm: py.path.local, *,
               exports: Optional[list[str]] = None,
               opt_level: int,
               debug_symbols: bool,
               ) -> py.path.local:
        """
        Compile the C code to WASM.
        """
        EXTRA_LDFLAGS = []
        if exports:
            for name in exports:
                EXTRA_LDFLAGS.append(f'-Wl,--export={name}')
        return self.cc(
            file_c,
            file_wasm,
            opt_level=opt_level,
            debug_symbols=debug_symbols,
            EXTRA_CFLAGS=self.WASM_CFLAGS,
            EXTRA_LDFLAGS=EXTRA_LDFLAGS
        )

    def c2exe(self, file_c: py.path.local, file_exe: py.path.local, *,
              opt_level: int,
              debug_symbols: bool,
              ) -> py.path.local:
        """
        Compile the C code to an executable
        """
        return self.cc(
            file_c,
            file_exe,
            opt_level=opt_level,
            debug_symbols=debug_symbols,
        )



class ZigToolchain(Toolchain):

    TARGET = 'wasi'

    def __init__(self, build_type: BUILD_TYPE) -> None:
        super().__init__(build_type)
        import ziglang  # type: ignore
        self.ZIG = py.path.local(ziglang.__file__).dirpath('zig')
        if not self.ZIG.check(exists=True):
            raise ValueError('Cannot find the zig executable; try pip install ziglang')

    @property
    def CC(self) -> list[str]:
        return [str(self.ZIG), 'cc']

    @property
    def WASM_CFLAGS(self) -> list[str]:
        # XXX all of this is very messy.
        #
        # For WASI we have two "exec-model":
        #   - "command": for standalone executables (this is the
        #     default)
        #   - "reactor": for staticaly-linked WASM modules which are called
        #     from the outside.
        #
        # For our tests, we need "reactor", WHICH FOR NOW IS HARCODED HERE.
        #
        # More info:
        #  https://clang.llvm.org/docs/ClangCommandLineReference.html#webassembly-driver
        # https://clang.llvm.org/docs/ClangCommandLineReference.html#webassembly-driver
        return super().WASM_CFLAGS + [
	    '--target=wasm32-wasi-musl',
            '-mexec-model=reactor',
        ]


class ClangToolchain(Toolchain):

    TARGET = 'wasi'

    @property
    def CC(self) -> list[str]:
        return ['clang']

    @property
    def WASM_CFLAGS(self) -> list[str]:
        return super().WASM_CFLAGS + [
	    '-mexec-model=reactor',
        ]


class NativeToolchain(Toolchain):

    TARGET = 'native'
    EXE_FILENAME_EXT = ''

    @property
    def CC(self) -> list[str]:
        return ['cc']


class EmscriptenToolchain(Toolchain):

    TARGET = 'emscripten'
    EXE_FILENAME_EXT = 'mjs'

    def __init__(self, build_type: BUILD_TYPE) -> None:
        super().__init__(build_type)
        self.EMCC = py.path.local.sysfind('emcc')
        if self.EMCC is None:
            raise ValueError('Cannot find the emcc executable')

    @property
    def CC(self) -> list[str]:
        return [str(self.EMCC)]

    @property
    def LDFLAGS(self) -> list[str]:
        post_js = spy.libspy.SRC.join('emscripten_extern_post.js')
        return super().LDFLAGS + [
            # "-sEXPORTED_FUNCTIONS=['_main']",
            "-sWASM_BIGINT",
            f"--extern-post-js={post_js}",
            # f"--post-js={}"
        ]

    def c2exe(self, file_c: py.path.local, file_exe: py.path.local, *,
              opt_level: int,
              debug_symbols: bool,
              ) -> py.path.local:

        return self.cc(
            file_c,
            file_exe,
            opt_level=opt_level,
            debug_symbols=debug_symbols,
            EXTRA_CFLAGS=self.WASM_CFLAGS,
        )
