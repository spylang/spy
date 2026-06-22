from dataclasses import dataclass, field
from typing import Callable, Literal

BuildTarget = Literal["native", "wasi", "emscripten"]
BuildType = Literal["release", "debug"]


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
