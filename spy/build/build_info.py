from dataclasses import dataclass, field
from typing import Callable, Literal

BuildTarget = Literal["native", "wasi", "emscripten"]
BuildType = Literal["release", "debug"]
OutputKind = Literal["exe", "testlib", "py-cffi"]

# Default SIMD vector width (in bits), used when --simd-width is not given.
SIMD_DEFAULT_WIDTH = 128

# SIMD widths (in bits) a build target may select.
SIMD_ALLOWED_WIDTHS: dict[BuildTarget, frozenset[int]] = {
    "native": frozenset({128, 256, 512}),
    "wasi": frozenset({128}),
    "emscripten": frozenset({128}),
}


@dataclass
class BuildInfo:
    # Absolute path strings produced by the module itself.
    include_dirs: list[str] = field(default_factory=list)
    headers: list[str] = field(default_factory=list)
    archives: list[str] = field(default_factory=list)
    # Passed verbatim to the C compiler/linker.
    cflags: list[str] = field(default_factory=list)
    ldflags: list[str] = field(default_factory=list)


BuildInfoFunc = Callable[[BuildTarget, BuildType], BuildInfo]
