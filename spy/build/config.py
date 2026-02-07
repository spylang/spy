import shutil
import subprocess
import sys
from dataclasses import dataclass
from os import getenv
from typing import Literal, Optional

import spy.libspy

BuildTarget = Literal["native", "wasi", "emscripten"]
OutputKind = Literal["exe", "lib", "py-cffi"]
BuildType = Literal["release", "debug"]
GCOption = Literal["none", "bdwgc"]


@dataclass
class BuildConfig:
    target: BuildTarget
    kind: OutputKind
    build_type: BuildType
    opt_level: Optional[int] = None
    warning_as_error: bool = False
    gc: GCOption = "none"


# ======= CFLAGS and LDFLAGS logic =======

# fmt: off
CFLAGS = [
    "--std=c99",
    "-Wfatal-errors",
    "-fdiagnostics-color=always",  # force colors
    "-I", str(spy.libspy.INCLUDE)
]
LDFLAGS = [
    "-lm"  # always include libm for now. Ideally we should do it only if needed
]

WARNING_CFLAGS = ["-Werror=implicit-function-declaration"]
WARNING_AS_ERROR_CFLAGS = ["-Werror", "-Wno-unreachable-code"]

RELEASE_CFLAGS  = ["-DSPY_RELEASE", "-O3", "-flto"]
RELEASE_LDFLAGS = ["-flto"]

DEBUG_CFLAGS    = ["-DSPY_DEBUG", "-O0", "-g"]
DEBUG_LDFLAGS: list[str] = []

WASM_CFLAGS = [
    "-mmultivalue",
    "-Xclang", "-target-abi",
    "-Xclang", "experimental-mv"
]
# fmt: on


class CompilerConfig:
    def __init__(self, config: BuildConfig):
        self.CC = ""
        self.ext = ""
        self.cflags = []
        self.ldflags = []

        self.cflags += CFLAGS
        self.cflags += [f"-DSPY_TARGET_{config.target.upper()}"]

        # e.g. 'spy/libspy/build/native/release/'
        self.ldflags += LDFLAGS
        libdir = spy.libspy.BUILD.join(config.target, config.build_type)
        self.ldflags += [
            "-L", str(libdir),
            "-lspy",
        ]  # fmt: skip

        if config.warning_as_error or getenv("SPY_WERROR") in ("true", "1"):
            self.cflags += WARNING_AS_ERROR_CFLAGS
        else:
            self.cflags += WARNING_CFLAGS

        if config.build_type == "release":
            self.cflags += RELEASE_CFLAGS
            self.ldflags += RELEASE_LDFLAGS
        else:
            self.cflags += DEBUG_CFLAGS
            self.ldflags += DEBUG_CFLAGS

        # target specific flags
        if config.target == "native":
            self.CC = "cc"
            self.ext = ""

        elif config.target == "wasi":
            # self.CC = 'zig cc'
            self.CC = "python -m ziglang cc"
            self.ext = ".wasm"
            self.cflags += WASM_CFLAGS
            self.cflags += ["--target=wasm32-wasi-musl"]
            self.ldflags += ["--target=wasm32-wasi-musl"]
            if config.kind == "lib":
                self.ldflags += ["-mexec-model=reactor"]

        elif config.target == "emscripten":
            self.CC = "emcc"
            self.ext = ".mjs"
            post_js = spy.libspy.SRC.join("emscripten_extern_post.js")
            self.cflags += WASM_CFLAGS
            self.ldflags += [
                "-sWASM_BIGINT",
                "-sERROR_ON_UNDEFINED_SYMBOLS=0",
                f"--extern-post-js={post_js}",
            ]

        else:
            assert False, f"Invalid target: {config.target}"

        if config.opt_level is not None:
            self.cflags += [f"-O{config.opt_level}"]

        # GC flags
        if config.gc == "bdwgc":
            self.cflags += ["-DSPY_GC_BDWGC"]
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
