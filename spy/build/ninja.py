from typing import Literal, Self
import subprocess
import textwrap
import shlex
import py.path
import spy.libspy
from spy.textbuilder import Color

TARGET = Literal['native', 'wasi', 'wasi-reactor', 'emscripten']
BUILD_TYPE = Literal['release', 'debug']

class Flags:
    """
    List of flags.

    Notable features:
      - str(l) returns a space-separated string of its items
      - individual items are escaped for ninja syntax
      - individual items are escaped ALSO for shell syntax.

    E.g.:
        flags = Flags(["a", "b", "c"])
        assert str(flags) == "a b c"

        flags = Flags(["spy_foo$bar"])
        assert str(flags) == "'spy_foo$$bar'"
    """

    def __init__(self, *items: str) -> None:
        self._items = list(items)

    def __iadd__(self, others: list[str]|Self) -> Self:
        if isinstance(others, Flags):
            self._items += others._items
        else:
            self._items += others
        return self

    def __repr__(self) -> None:
        return f'Flags({self._items})'

    def __str__(self) -> str:
        def escape(s: str) -> str:
            return shlex.quote(s.replace('$', '$$'))
        return ' '.join([escape(item) for item in self._items])


CFLAGS = Flags(
    '--std=c99',
    '-Werror=implicit-function-declaration',
    '-Wfatal-errors',
    '-fdiagnostics-color=always', # force colors
    '-I', str(spy.libspy.INCLUDE),
)
RELEASE_CFLAGS = Flags('-DSPY_RELEASE', '-O3')
DEBUG_CFLAGS   = Flags('-DSPY_DEBUG',   '-O0', '-g')

WASM_CFLAGS = Flags(
    '-mmultivalue',
    '-Xclang', '-target-abi',
    '-Xclang', 'experimental-mv'
)



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
        self.out = None

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
        cflags = Flags()
        ldflags = Flags()
        extra_cflags = Flags()
        extra_ldflags = Flags()

        cflags += CFLAGS
        if self.build_type == 'release':
            cflags += RELEASE_CFLAGS
        else:
            cflags += DEBUG_CFLAGS

        # XXX: we are abusing 'target' here: we should have the notion of
        # 'platform' (wasi, native, etc) and 'output_kind' (exe or lib)
        t = self.target
        if t == 'wasi-reactor':
            t = 'wasi'
        cflags += [
            f'-DSPY_TARGET_{t.upper()}'
        ]

        ldflags += [
            '-L', str(self.libdir()),
            '-lspy'
        ]

        # target specific flags
        if self.target == 'native':
            CC = 'cc'
            self.out = basename

        elif self.target == 'wasi-reactor':
            CC = 'zig cc'
            self.out = basename + '.wasm'
            extra_cflags += WASM_CFLAGS
            extra_cflags += [
                '--target=wasm32-wasi-musl',
            ]
            extra_ldflags += [
                '--target=wasm32-wasi-musl',
                '-mexec-model=reactor'
            ]
            extra_ldflags += [f'-Wl,--export={name}' for name in wasm_exports]

        elif self.target == 'wasi':
            CC = 'zig cc'
            self.out = basename + '.wasm'
            extra_cflags = WASM_CFLAGS
            extra_cflags += [
                '--target=wasm32-wasi-musl'
            ]
            extra_ldflags += [
                '--target=wasm32-wasi-musl'
            ]

        elif self.target == 'emscripten':
            CC = 'emcc'
            self.out = basename + '.mjs'
            post_js = spy.libspy.SRC.join('emscripten_extern_post.js')
            extra_cflags += WASM_CFLAGS
            extra_ldflags += [
                "-sWASM_BIGINT",
                "-sERROR_ON_UNDEFINED_SYMBOLS=0",
                f"--extern-post-js={post_js}",
            ]

        # ===== generate build.ninja =======

        build_ninja = self.build_dir.join('build.ninja')
        with build_ninja.open('w') as f:
            f.write(textwrap.dedent(f"""
            cc = {CC}

            cflags = {cflags}
            cflags = $cflags {extra_cflags}

            ldflags = {ldflags}
            ldflags = $ldflags {extra_ldflags}

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
            f.write(f'build {self.out}: link {s_ofiles}\n')
            f.write(f'default {self.out}\n')

    def build(self) -> py.path.local:
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
        return self.build_dir.join(self.out)
