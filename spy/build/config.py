from typing import Literal, Optional
from dataclasses import dataclass

BuildTarget = Literal['native', 'wasi', 'emscripten']
OutputKind = Literal['exe', 'lib', 'py:cffi']
BuildType = Literal['release', 'debug']

@dataclass
class BuildConfig:
    target: BuildTarget
    kind: OutputKind
    build_type: BuildType
    opt_level: Optional[int] = None
