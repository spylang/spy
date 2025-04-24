from typing import Literal, Self, Optional
import subprocess
import textwrap
import shlex
import py.path
import spy.libspy
from spy.textbuilder import TextBuilder, Color

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

    def append(self, s: str) -> None:
        self._items.append(s)

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
    target: TARGET
    build_type: BUILD_TYPE
    build_dir: py.path.local
    opt_level: Optional[int]
    CC: Optional[str]
    out: Optional[str]
    cflags: Flags
    ldflags: Flags

    def __init__(
            self,
            *,
            target: TARGET,
            build_type: BUILD_TYPE,
            build_dir: py.path.local,
            opt_level: Optional[int] = None,
    ) -> None:
        self.target = target
        self.build_type = build_type
        self.build_dir = build_dir
        self.opt_level = opt_level
        self.cc = None
        self.out = None
        self.cflags = Flags()
        self.ldflags = Flags()

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

        self.cflags += CFLAGS
        if self.build_type == 'release':
            self.cflags += RELEASE_CFLAGS
        else:
            self.cflags += DEBUG_CFLAGS

        # XXX: we are abusing 'target' here: we should have the notion of
        # 'platform' (wasi, native, etc) and 'output_kind' (exe or lib)
        t = self.target
        if t == 'wasi-reactor':
            t = 'wasi'
        self.cflags += [
            f'-DSPY_TARGET_{t.upper()}'
        ]

        self.ldflags += [
            '-L', str(self.libdir()),
            '-lspy'
        ]

        # target specific flags
        if self.target == 'native':
            self.CC = 'cc'
            self.out = basename

        elif self.target == 'wasi-reactor':
            self.CC = 'zig cc'
            self.out = basename + '.wasm'
            self.cflags += WASM_CFLAGS
            self.cflags += [
                '--target=wasm32-wasi-musl',
            ]
            self.ldflags += [
                '--target=wasm32-wasi-musl',
                '-mexec-model=reactor'
            ]
            self.ldflags += [f'-Wl,--export={name}' for name in wasm_exports]

        elif self.target == 'wasi':
            self.CC = 'zig cc'
            self.out = basename + '.wasm'
            self.cflags += WASM_CFLAGS
            self.cflags += [
                '--target=wasm32-wasi-musl'
            ]
            self.ldflags += [
                '--target=wasm32-wasi-musl'
            ]

        elif self.target == 'emscripten':
            self.CC = 'emcc'
            self.out = basename + '.mjs'
            post_js = spy.libspy.SRC.join('emscripten_extern_post.js')
            self.cflags += WASM_CFLAGS
            self.ldflags += [
                "-sWASM_BIGINT",
                "-sERROR_ON_UNDEFINED_SYMBOLS=0",
                f"--extern-post-js={post_js}",
            ]

        if self.opt_level is not None:
            self.cflags += [f'-O{self.opt_level}']

        # generate build.ninja
        build_ninja = self.build_dir.join('build.ninja')
        with build_ninja.open('w') as f:
            if len(cfiles) == 1:
                s = self.gen_build_ninja_single(cfiles[0])
            else:
                s = self.gen_build_ninja_many(cfiles)
            f.write(s)

    def gen_build_ninja_single(self, cfile: py.path.local) -> str:
        """
        Generate a build.ninja optimized for a single .c file.

        It collapses CC and LINK together, so avoid invoking it twice. This is
        a tiny optimization but it's important because it's used by almost all
        the tests, so it shaves several seconds from total testing time.
        """
        tb = TextBuilder()
        tb.wb(f"""
        cc = {self.CC}
        cflags = {self.cflags}
        ldflags = {self.ldflags}

        rule cc
          command = $cc $in -o $out $cflags $ldflags
          description = CC $out
        """)
        c = cfile.relto(self.build_dir)
        tb.wl('')
        tb.wl(f'build {self.out}: cc {c}')
        tb.wl(f'default {self.out}')
        return tb.build()

    def gen_build_ninja_many(self, cfiles: list[py.path.local]) -> str:
        tb = TextBuilder()
        tb.wb(f"""
        cc = {self.CC}
        cflags = {self.cflags}
        ldflags = {self.ldflags}

        rule cc
          command = $cc $cflags -MMD -MF $out.d -c $in -o $out
          description = CC $out
          depfile = $out.d
          deps = gcc

        rule link
          command = $cc $in -o $out $ldflags
          description = LINK $out
        """)
        tb.wl('')
        ofiles = Flags()
        for cfile in cfiles:
            ofile = cfile.new(ext='.o')
            c = cfile.relto(self.build_dir)
            o = ofile.relto(self.build_dir)
            ofiles.append(o)
            tb.wl(f'build {o}: cc {c}')
        tb.wl(f'build {self.out}: link {ofiles}')
        tb.wl(f'default {self.out}')

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
