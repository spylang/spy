from typing import Literal, Optional
from dataclasses import dataclass
import spy.libspy

BuildTarget = Literal['native', 'wasi', 'emscripten']
OutputKind = Literal['exe', 'lib', 'py-cffi']
BuildType = Literal['release', 'debug']

@dataclass
class BuildConfig:
    target: BuildTarget
    kind: OutputKind
    build_type: BuildType
    opt_level: Optional[int] = None


# ======= CFLAGS and LDFLAGS logic =======

CFLAGS = [
    '--std=c99',
    '-Werror=implicit-function-declaration',
    '-Wfatal-errors',
    '-fdiagnostics-color=always', # force colors
    '-I', str(spy.libspy.INCLUDE),
]
RELEASE_CFLAGS = ['-DSPY_RELEASE', '-O3']
DEBUG_CFLAGS   = ['-DSPY_DEBUG',   '-O0', '-g']

WASM_CFLAGS = [
    '-mmultivalue',
    '-Xclang', '-target-abi',
    '-Xclang', 'experimental-mv'
]

class CompilerConfig:

    def __init__(self, config: BuildConfig):
        self.CC = ''
        self.ext = ''
        self.cflags = []
        self.ldflags = []

        self.cflags += CFLAGS
        self.cflags += [
            f'-DSPY_TARGET_{config.target.upper()}'
        ]
        if config.build_type == 'release':
            self.cflags += RELEASE_CFLAGS
        else:
            self.cflags += DEBUG_CFLAGS

        # e.g. 'spy/libspy/build/native/release/'
        libdir = spy.libspy.BUILD.join(config.target, config.build_type)
        self.ldflags += [
            '-L', str(libdir),
            '-lspy'
        ]

        # target specific flags
        if config.target == 'native':
            self.CC = 'cc'
            self.ext = ''

        elif config.target == 'wasi':
            #self.CC = 'zig cc'
            self.CC = 'python -m ziglang cc'
            self.ext = '.wasm'
            self.cflags += WASM_CFLAGS
            self.cflags += [
                '--target=wasm32-wasi-musl'
            ]
            self.ldflags += [
                '--target=wasm32-wasi-musl'
            ]
            if config.kind == 'lib':
                self.ldflags += [
                    '-mexec-model=reactor'
                ]

        elif config.target == 'emscripten':
            self.CC = 'emcc'
            self.ext = '.mjs'
            post_js = spy.libspy.SRC.join('emscripten_extern_post.js')
            self.cflags += WASM_CFLAGS
            self.ldflags += [
                "-sWASM_BIGINT",
                "-sERROR_ON_UNDEFINED_SYMBOLS=0",
                f"--extern-post-js={post_js}",
            ]

        else:
            assert False, f'Invalid target: {config.target}'

        if config.opt_level is not None:
            self.cflags += [f'-O{config.opt_level}']
