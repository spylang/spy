from typing import Literal
import subprocess
import textwrap
import py.path
import spy.libspy
from spy.textbuilder import Color

TARGET = Literal['native', 'wasi', 'wasi-reactor', 'emscripten']
BUILD_TYPE = Literal['release', 'debug']

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


class NinjaWriter:

    def __init__(
            self,
            target: TARGET,
            build_type: BUILD_TYPE,
            build_dir: py.path.local
    ) -> None:
        self.target = target
        self.build_type = build_type
        self.build_dir = build_dir

    def libdir(self):
        t = self.target
        if t == 'wasi-reactor':
            t = 'wasi'
        return spy.libspy.BUILD.join(t, self.build_type)

    def write(
            self,
            basename: str,
            cfiles: list[py.path.local],
            *,
            wasm_exports: list[str] = [],
    ) -> None:
        # ======== compute cflags and ldflags ========
        cflags = CFLAGS[:]
        if self.build_type == 'release':
            cflags += RELEASE_CFLAGS
        else:
            cflags += DEBUG_CFLAGS
        cflags += [
            f'-DSPY_TARGET_{self.target.upper()}'
        ]

        ldflags = ['-L', str(self.libdir()), '-lspy']

        # target specific flags
        if self.target == 'native':
            CC = 'cc'
            out = basename
            extra_cflags = []
            extra_ldflags = []

        elif self.target == 'wasi-reactor':
            CC = 'zig cc'
            out = basename + '.wasm'
            extra_cflags = WASM_CFLAGS + [
                '--target=wasm32-wasi-musl',
                '-mexec-model=reactor'
            ]
            extra_ldflags = [f'-Wl,--export={name}' for name in wasm_exports]

        elif self.target == 'wasi':
            CC = 'zig cc'
            out = basename + '.wasm'
            extra_cflags = WASM_CFLAGS + [
                '--target=wasm32-wasi-musl'
            ]
            extra_ldflags = []

        elif self.target == 'emscripten':
            CC = 'emcc'
            out = basename + '.mjs'
            post_js = spy.libspy.SRC.join('emscripten_extern_post.js')
            extra_cflags = WASM_CFLAGS[:]
            extra_ldflags = [
                "-sWASM_BIGINT",
                "-sERROR_ON_UNDEFINED_SYMBOLS=0",
                f"--extern-post-js={post_js}",
            ]

        # ===== generate build.ninja =======

        build_ninja = self.build_dir.join('build.ninja')
        #cfiles = [f.relto(self.build_dir) for f in cfiles]

        s_cflags = ' '.join(cflags)
        s_ldflags = ' '.join(ldflags)
        s_extra_cflags = ' '.join(extra_cflags)
        s_extra_ldflags = ' '.join(extra_ldflags)

        with build_ninja.open('w') as f:
            f.write(textwrap.dedent(f"""
            cc = {CC}

            cflags = {s_cflags}
            cflags = $cflags {s_extra_cflags}

            ldflags = {s_ldflags}
            ldflags = $ldflags {s_extra_ldflags}

            rule cc
              command = $cc $cflags -MMD -MF $out.d -c $in -o $out
              description = CC $out
              depfile = $out.d
              deps = gcc

            rule link
              command = $cc $in -o $out $ldflags
              description = LINK $out
            """))
            f.write('\n')

            ofiles = []
            for cfile in cfiles:
                ofile = cfile.new(ext='.o')
                c = cfile.relto(self.build_dir)
                o = ofile.relto(self.build_dir)
                ofiles.append(o)
                f.write(f'build {o}: cc {c}\n')

            s_ofiles = ' '.join(ofiles)
            f.write(f'build {out}: link {s_ofiles}\n')
            f.write(f'default {out}\n')

    def build(self) -> None:
        cmdline = ['ninja', '-C', str(self.build_dir)]
        #print(" ".join(cmdline))
        proc = subprocess.run(
            cmdline,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        if proc.returncode != 0:
            FORCE_COLORS = True
            lines = ["Compilation failed!"]
            lines.append(' '.join(cmdline))
            lines.append('')
            errlines = proc.stdout.decode('utf-8').splitlines()
            if FORCE_COLORS:
                errlines = [Color.set('default', line) for line in errlines]
            lines += errlines
            msg = '\n'.join(lines)
            raise Exception(msg)
        #return file_out
