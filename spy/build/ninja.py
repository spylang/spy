import shlex
from typing import Optional

import py.path

from spy.build.config import BuildConfig, CompilerConfig
from spy.errors import WIP
from spy.textbuilder import TextBuilder
from spy.util import robust_run


def fmt_flags(flags: list[str]) -> str:
    """
    Format a list of CFLAGS/LDFLAGS into ninja-compatible format:

      - space-separated string of its items
      - individual items are escaped for ninja syntax
      - individual items are escaped ALSO for shell syntax.

    E.g.:
        >>> fmt_flags(["a", "b", "c"])
        "a b c"

        >>> fmt_flags(["spy_foo$bar"])
        "'spy_foo$$bar'"
    """

    def escape(s: str) -> str:
        return shlex.quote(s.replace("$", "$$"))
    return " ".join([escape(item) for item in flags])


class NinjaWriter:
    config: BuildConfig
    build_dir: py.path.local
    out: Optional[str]

    def __init__(self, config: BuildConfig, build_dir: py.path.local) -> None:
        # for now, we support only some combinations of target/kind
        if config.kind == "lib":
            if config.target not in ("wasi", "emscripten"):
                raise WIP("--output-kind=lib works only for wasi and emscripten targets")
        self.config = config
        self.build_dir = build_dir
        self.out = None

    def write(
            self,
            basename: str,
            cfiles: list[py.path.local],
            *,
            wasm_exports: list[str] = [],
    ) -> None:
        comp = CompilerConfig(self.config)
        self.out = basename + comp.ext
        if self.config.kind == "lib":
            comp.ldflags += [
                f"-Wl,--export={name}" for name in wasm_exports
            ]

        # generate build.ninja
        build_ninja = self.build_dir.join("build.ninja")
        with build_ninja.open("w") as f:
            if len(cfiles) == 1:
                s = self.gen_build_ninja_single(comp, cfiles[0])
            else:
                s = self.gen_build_ninja_many(comp, cfiles)
            f.write(s)

    def gen_build_ninja_single(
            self,
            comp: CompilerConfig,
            cfile: py.path.local
    ) -> str:
        """
        Generate a build.ninja optimized for a single .c file.

        It collapses CC and LINK together, so avoid invoking it twice. This is
        a tiny optimization but it's important because it's used by almost all
        the tests, so it shaves several seconds from total testing time.
        """
        CC = comp.CC
        cflags = fmt_flags(comp.cflags)
        ldflags = fmt_flags(comp.ldflags)

        tb = TextBuilder()
        tb.wb(f"""
        cc = {CC}
        cflags = {cflags}
        ldflags = {ldflags}

        rule cc
          command = $cc $in -o $out $cflags $ldflags
          description = CC $out
        """)
        c = cfile.relto(self.build_dir)
        if c == "":
            # this means that cfile is not inside build_dir, use abspath
            c = str(cfile)
        tb.wl("")
        tb.wl(f"build {self.out}: cc {c}")
        tb.wl(f"default {self.out}")
        return tb.build()

    def gen_build_ninja_many(
            self,
            comp: CompilerConfig,
            cfiles: list[py.path.local]
    ) -> str:
        CC = comp.CC
        cflags = fmt_flags(comp.cflags)
        ldflags = fmt_flags(comp.ldflags)

        tb = TextBuilder()
        tb.wb(f"""
        cc = {CC}
        cflags = {cflags}
        ldflags = {ldflags}

        rule cc
          command = $cc $cflags -MMD -MF $out.d -c $in -o $out
          description = CC $out
          depfile = $out.d
          deps = gcc

        rule link
          command = $cc $in -o $out $ldflags
          description = LINK $out
        """)
        tb.wl("")
        ofiles = []
        for cfile in cfiles:
            ofile = cfile.new(ext=".o")
            c = cfile.relto(self.build_dir)
            o = ofile.relto(self.build_dir)
            ofiles.append(o)
            tb.wl(f"build {o}: cc {c}")

        ofiles_s = fmt_flags(ofiles)
        tb.wl(f"build {self.out}: link {ofiles_s}")
        tb.wl(f"default {self.out}")
        return tb.build()

    def build(self) -> py.path.local:
        assert self.out is not None
        cmdline = ["ninja", "-C", str(self.build_dir)]
        # unbuffer run to get gcc to emit color codes
        robust_run(cmdline, unbuffer=True)
        return self.build_dir.join(self.out)
