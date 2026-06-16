"""
SPy out-of-tree builtin VM module wrapping the *system* libmagic library (the
engine behind the Unix `file` command).

To be loaded via:
    spy --extra-vm-module ../spyvm_libmagic demo/read_magic.spy

or by listing this package in the project's spy.toml:
    extra-vm-modules = ["../spyvm_libmagic"]

This example differs from `spyvm_qrcodegen` in one key way: libmagic is an
*external* system library, installed via the OS package manager:

    apt install libmagic-dev      # Debian/Ubuntu
    brew install libmagic         # macOS

We do NOT vendor its source and we do NOT have a WASM build of it. The C half
(src/spyvm_libmagic.c) is our own glue, compiled to a native-only archive; the
final binary additionally links the system library with `-lmagic`.

Consequences:
  - The module works only with the C backend (`spy build`), targeting `native`.
    Under wasi, build_info returns no archives and no ldflags, so the SPy
    interpreter cannot call into libmagic: the builtin functions below raise
    NotImplementedError when executed in interpreted mode.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from spy.build.build_info import BuildInfo, BuildTarget, BuildType
from spy.vm.bytes import W_Bytes
from spy.vm.registry import ModuleRegistry
from spy.vm.str import W_Str

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

MODULE = ModuleRegistry("magic")

HERE = Path(__file__).parent


def build_info(target: BuildTarget, build_type: BuildType) -> BuildInfo:
    if target == "wasi":
        # no wasi build of libmagic; the builtins raise NotImplementedError
        archives: list[str] = []
        ldflags: list[str] = []
    else:
        archives = [f"{HERE}/build/{target}/{build_type}/spyvm_libmagic.a"]
        ldflags = ["-lmagic"]
    return BuildInfo(
        include_dirs=[f"{HERE}/src"],
        headers=[f"{HERE}/src/spyvm_libmagic.h"],
        archives=archives,
        ldflags=ldflags,
    )


@MODULE.builtin_func
def w_describe(vm: "SPyVM", w_data: W_Bytes) -> W_Str:
    raise NotImplementedError(
        "magic.describe() is not available in interpreted mode: "
        "libmagic has no WASM build. Compile with the C backend instead."
    )


@MODULE.builtin_func
def w_mime(vm: "SPyVM", w_data: W_Bytes) -> W_Str:
    raise NotImplementedError(
        "magic.mime() is not available in interpreted mode: "
        "libmagic has no WASM build. Compile with the C backend instead."
    )
