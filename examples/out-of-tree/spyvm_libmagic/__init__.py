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
(src/libmagic_spy.c) is our own glue, compiled to a native-only archive; the
final binary additionally links the system library with `-lmagic`.

Consequences:
  - The module works only with the C backend (`spy build`), targeting `native`.
    There is no `wasm_archives`, so the SPy interpreter cannot call into
    libmagic: the builtin functions below raise NotImplementedError when
    executed in interpreted mode.
"""

from typing import TYPE_CHECKING

import py.path

from spy.vm.bytes import W_Bytes
from spy.vm.registry import CModuleBuildInfo, ModuleRegistry
from spy.vm.str import W_Str

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

# The module name as seen by SPy code (`import magic`).
MODULE = ModuleRegistry("magic")

_HERE = py.path.local(__file__).dirpath()

# No wasm_archives: libmagic has no WASM build, so the interpreter cannot call
# into it (see the NotImplementedError raised by the builtins below).
MODULE.wasm_archives = []

MODULE.build_info = CModuleBuildInfo(
    # Our own glue, built native-only by the Makefile.
    archive_specs=[(_HERE.join("build"), "libmagic_spy.a")],
    include_dirs=[_HERE.join("src")],
    headers=[_HERE.join("src", "libmagic_spy.h")],
)

# TODO: the final binary also needs to link the external system library with
# `-lmagic`. CModuleBuildInfo does not yet have a way to express "link this
# system library"; this is the build-system extension we will design next.
# Conceptually we want something like:
#     MODULE.build_info.libraries = ["magic"]


@MODULE.builtin_func
def w_describe(vm: "SPyVM", w_data: W_Bytes) -> W_Str:
    """
    Return a human-readable description of the given bytes, e.g.
    "PNG image data, 640 x 480, 8-bit/color RGB". This is what `file` prints.
    """
    raise NotImplementedError(
        "magic.describe() is not available in interpreted mode: "
        "libmagic has no WASM build. Compile with the C backend instead."
    )


@MODULE.builtin_func
def w_mime(vm: "SPyVM", w_data: W_Bytes) -> W_Str:
    """
    Return the MIME type of the given bytes, e.g. "image/png". Equivalent to
    `file --mime-type`.
    """
    raise NotImplementedError(
        "magic.mime() is not available in interpreted mode: "
        "libmagic has no WASM build. Compile with the C backend instead."
    )
