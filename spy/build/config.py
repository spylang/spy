import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Literal, Optional

import py.path

import spy.libspy
from spy.build.build_info import (
    SIMD_ALLOWED_WIDTHS,
    SIMD_DEFAULT_WIDTH,
    BuildTarget,
    BuildType,
    OutputKind,
)
from spy.build.flags import get_cc, get_cflags, get_ldflags, get_libdir
from spy.errors import WIP

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
    # SIMD vector width in bytes, or None to use the per-target default.
    # This is a *static*, build-time configuration: it is fixed before
    # redshift, because redshift runs before the final C compiler.
    # See `resolve_simd_width` / `simd_width_of`.
    simd_width: Optional[int] = None
    # Value passed as `-march=<march>` to the C compiler (e.g. "native",
    # "x86-64-v3", "znver4"). None means "don't pass -march at all", i.e.
    # the compiler's default baseline ISA for the target (e.g. plain SSE2
    # on x86-64). Only meaningful for --target native[-static]: the C
    # compiler is the one that decides how a `--simd-width` wider than one
    # native register gets legalized, so --simd-width and --march need to
    # be chosen together to get genuine wide-SIMD codegen instead of the
    # compiler silently splitting/scalarizing.
    march: Optional[str] = None

    def __post_init__(self) -> None:
        if self.kind == "testlib" and self.target not in ("wasi", "emscripten"):
            raise WIP(
                "--output-kind=testlib works only for wasi and emscripten targets"
            )
        self._simd_width = resolve_simd_width(self.target, self.simd_width)

    @property
    def effective_simd_width(self) -> int:
        return self._simd_width


def resolve_simd_width(target: BuildTarget, override: Optional[int]) -> int:
    """
    Return the effective SIMD vector width (in bytes) for a build.

    The width is a *static*, build-time configuration: it is fixed before
    redshift, because redshift runs before the final C compiler / `-march=`
    is pinned, so per-target autodetection is not possible at redshift time.
    The default (128) is universally safe.

    `--simd-width=256`/`512` opt into wider native vectors
    (the user is responsible for matching `-march`).

    `override` is the value of `--simd-width` (or `None`); it must be one
    of `SIMD_ALLOWED_WIDTHS[target]`.
    """
    if override is None:
        return SIMD_DEFAULT_WIDTH
    allowed = SIMD_ALLOWED_WIDTHS[target]
    if override not in allowed:
        allowed_str = "/".join(str(w) for w in sorted(allowed))
        raise ValueError(
            f"--simd-width={override} is not valid for target {target!r}; "
            f"allowed: {allowed_str}"
        )
    return override


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

        self.ldflags += LDFLAGS

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

        if config.march is not None:
            # Validated at the CLI level (build.py) to only be used with
            # --target native / native-static; asserted here as a
            # cheap last-resort check in case BuildConfig is constructed
            # directly (e.g. from tests) rather than via the CLI.
            assert config.target == "native", (
                f"--march is only supported for --target native "
                f"(including --static), got target={config.target!r}"
            )
            self.cflags += [f"-march={config.march}"]

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
