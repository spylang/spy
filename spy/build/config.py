import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Literal, Optional

import py.path

import spy.libspy
from spy.build.build_info import BuildTarget, BuildType, OutputKind
from spy.build.flags import get_cc, get_cflags, get_ldflags, get_libdir
from spy.errors import WIP, SPyError

GCOption = Literal["none", "bdwgc"]


@dataclass
class BuildConfig:
    target: BuildTarget
    kind: OutputKind
    build_type: BuildType
    opt_level: Optional[int] = None
    warning_as_error: bool = False
    gc: GCOption = "none"
    static: bool = False

    def __post_init__(self) -> None:
        if self.kind == "testlib" and self.target not in ("wasi", "emscripten"):
            raise WIP(
                "--output-kind=testlib works only for wasi and emscripten targets"
            )


# ======= CFLAGS and LDFLAGS logic =======

# fmt: off
EXTRA_CFLAGS = [
    "--std=c99",
    "-Wfatal-errors",
    "-fdiagnostics-color=always",  # force colors
]
LDFLAGS = [
    "-lm"  # always include libm for now. Ideally we should do it only if needed
]

# fmt: on


class CompilerConfig:
    def __init__(self, config: BuildConfig):
        self.CC = ""
        self.ext = ""
        self.cflags = []
        self.ldflags = []

        if config.static:
            assert config.target == "native"
            flags_target = "native-static"
        else:
            flags_target = config.target

        self.CC = get_cc(flags_target)
        self.cflags += get_cflags(
            flags_target, config.build_type, config.kind, config.warning_as_error
        )
        self.cflags += EXTRA_CFLAGS

        self.ldflags += get_ldflags(flags_target, config.build_type)

        libdir = get_libdir(flags_target, config.build_type, config.kind)
        if config.target == "wasi" and config.kind == "testlib":
            # WASM testlibs are used by tests: in this case we want to make sure to
            # include the whole libspy.a, so that helper functions such as spy_str_alloc
            # are always available.
            #
            # If you don't pass --whole-archive, the linker will silently discard all
            # the .o files which are not used (so e.g. if you never call any str_*
            # function, str.o is discarded and spy_str_alloc is not present at all).
            libspy_a = str(py.path.local(libdir).join("libspy.a"))
            self.ldflags += [
                "-Wl,--whole-archive",
                libspy_a,
                "-Wl,--no-whole-archive",
            ]  # fmt: skip
        else:
            self.ldflags += [
                "-L", libdir,
                "-lspy",
            ]  # fmt: skip

        # target specific flags
        if config.target == "native":
            self.ext = ""

        elif config.target == "wasi":
            self.ext = ".wasm"
            if config.kind == "testlib":
                self.ldflags += ["-mexec-model=reactor"]

        elif config.target == "emscripten":
            self.ext = ".mjs"
            post_js = spy.libspy.SRC.join("emscripten_extern_post.js")
            pre_js = spy.libspy.SRC.join("emscripten_pre.js")
            self.ldflags += [
                "-sWASM_BIGINT",
                "-sEXPORTED_RUNTIME_METHODS=HEAP8",  # for exporting function in wasm, and running on CI
                f"--pre-js={pre_js}",
                f"--extern-post-js={post_js}",
            ]

        else:
            assert False, f"Invalid target: {config.target}"

        if config.opt_level is not None:
            self.cflags += [f"-O{config.opt_level}"]

        # GC flags
        if config.gc == "bdwgc":
            self.cflags = [f for f in self.cflags if f != "-DSPY_GC_NONE"]
            self.cflags += ["-DSPY_GC_BDWGC"]
            self.add_libgc(config)

        # NOTE: it's important that `-lm` (which is included in LDFLAGS) is placed
        # towards the end, and in particular AFTER -lspy.
        #
        # This is because on some platforms (at least linux/ubuntu) `ld` passes
        # --as-needed by default: libraries are included only if they are needed AT THE
        # TIME THEY ARE CONSIDERED.  LD flags are scanned left-to-right, and order is
        # important:
        #
        #     - "-lspy -lm": ld sees libspy first, which needs libm; then it seems
        #       libm, and decides to keep it. GOOD.
        #
        #     - "-lm -lspy": ld sees libm, which is not needed, and SILENTLY DISCARDS
        #       IT. Then it sees libspy, which needs libm, but this dependency stays -
        #       unfulfilled. BAD!
        #
        # The thumb rule is: things that need symbols go on the left, things that
        # provide them go on the right
        self.ldflags += LDFLAGS

    def add_libgc(self, config: BuildConfig) -> None:
        # where do we find libgc? We support the following configurations:
        #
        #   1. --static builds: we use our vendored copy of libgc.a
        #   2. conda/pixi env: we use the bdw-gc package installed in the env
        #   3. homebrew installation on maxOS
        #   4. system-wide libraries as a fallback
        #
        # Case (4) is e.g. what you get on ubuntu if you do `apt install libgc`
        conda_prefix = os.environ.get("CONDA_PREFIX")

        if config.static:
            # 1. --static builds
            self._build_bdwgc_static()
            gc_prefix = str(spy.libspy.DEPS.join("build", "native-static"))
            self.cflags += ["-I", f"{gc_prefix}/include"]
            self.ldflags += ["-L", f"{gc_prefix}/lib", "-lgc"]
            return

        elif conda_prefix is not None:
            # 2. conda/pixi env, bgw-gc package
            gc_h = py.path.local(conda_prefix).join("include", "gc.h")
            if not gc_h.check(exists=True):
                raise SPyError("W_Exception", "conda package bdw-gc is not installed")

            self.cflags += ["-I", f"{conda_prefix}/include"]
            self.ldflags += ["-L", f"{conda_prefix}/lib"]
            # conda-forge libgc has an @rpath install name: without an
            # rpath entry the executable won't find it at runtime
            self.ldflags += [f"-Wl,-rpath,{conda_prefix}/lib"]
            self.ldflags += ["-lgc"]
            return

        elif sys.platform == "darwin" and shutil.which("brew"):
            # 3. homebrew on macOS: check whether bdw-gc is present, else fallback
            prefix = subprocess.run(
                ["brew", "--prefix", "bdw-gc"],
                capture_output=True,
                text=True,
            ).stdout.strip()
            if prefix:
                self.cflags += ["-I", f"{prefix}/include"]
                self.ldflags += ["-L", f"{prefix}/lib"]
                return

        # 4. fallback, let's hope libgc is installed system-wide
        self.ldflags += ["-lgc"]

    @staticmethod
    def _build_bdwgc_static() -> None:
        deps_dir = str(spy.libspy.DEPS)
        libgc = spy.libspy.DEPS.join("build", "native-static", "lib", "libgc.a")
        if libgc.check(file=True):
            return
        subprocess.run(
            ["make", "-C", deps_dir, "TARGET=native-static", "bdwgc"],
            check=True,
        )
