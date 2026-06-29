import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Literal, Optional

import spy.libspy
from spy.build.build_info import BuildTarget, BuildType
from spy.build.flags import get_cc, get_cflags, get_ldflags, get_libdir

OutputKind = Literal["exe", "lib", "py-cffi"]
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
            flags_target, config.build_type, config.warning_as_error
        )
        self.cflags += EXTRA_CFLAGS

        self.ldflags += LDFLAGS
        self.ldflags += get_ldflags(flags_target, config.build_type)

        libdir = get_libdir(flags_target, config.build_type)
        if config.target == "wasi" and config.kind == "lib":
            # WASM libs are mostly used by tests: in this case we want to make sure to
            # include the whole libspy.a, so that helper functions such as spy_str_alloc
            # are always available.
            #
            # If you don't pass --whole-archive, the linker will silently discard all
            # the .o files which are not used (so e.g. if you never call any str_*
            # function, str.o is discarded and spy_str_alloc is not present at all).
            libspy_a = str(
                spy.libspy.BUILD.join(flags_target, config.build_type, "libspy.a")
            )
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
            if config.kind == "lib":
                self.ldflags += ["-mexec-model=reactor"]

        elif config.target == "emscripten":
            self.ext = ".mjs"
            post_js = spy.libspy.SRC.join("emscripten_extern_post.js")
            self.ldflags += [
                "-sWASM_BIGINT",
                "-sERROR_ON_UNDEFINED_SYMBOLS=0",
                "-sEXPORTED_RUNTIME_METHODS=HEAP8",  # for exporting function in wasm, and running on CI
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
            if config.static:
                self._build_bdwgc_static()
                gc_prefix = str(spy.libspy.DEPS.join("build", "native-static"))
                self.cflags += ["-I", f"{gc_prefix}/include"]
                self.ldflags += ["-L", f"{gc_prefix}/lib", "-lgc"]
            else:
                self.ldflags += ["-lgc"]
                # On macOS, Homebrew installs bdw-gc outside the default
                # compiler search paths
                if sys.platform == "darwin" and shutil.which("brew"):
                    prefix = subprocess.run(
                        ["brew", "--prefix", "bdw-gc"],
                        capture_output=True,
                        text=True,
                    ).stdout.strip()
                    if prefix:
                        self.cflags += ["-I", f"{prefix}/include"]
                        self.ldflags += ["-L", f"{prefix}/lib"]

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
