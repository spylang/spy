from dataclasses import dataclass, field


@dataclass
class BuildInfo:
    # Absolute path strings produced by the module itself.
    include_dirs: list[str] = field(default_factory=list)
    headers: list[str] = field(default_factory=list)
    archives: list[str] = field(default_factory=list)
    # Passed verbatim to the C compiler/linker.
    cflags: list[str] = field(default_factory=list)
    ldflags: list[str] = field(default_factory=list)
