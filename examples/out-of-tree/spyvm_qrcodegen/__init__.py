"""
SPy out-of-tree builtin VM module wrapping the qrcodegen C library.

To be loaded via:
    spy --extra-vm-module ../spyvm_qrcodegen demo/main.spy

or by listing this package in the project's spy.toml:
    extra-vm-modules = ["../spyvm_qrcodegen"]

The package exposes a single name `MODULE` which is an instance of
ModuleRegistry. The SPy CLI imports this package and reads `MODULE` to
discover the module's name, contents, and C-build metadata.

The C half lives in src/spyvm_qrcodegen.c; it #includes libspy's public
headers and the vendored qrcodegen headers, and exposes three WASM exports
(spy_qrcodegen$encode, $get_size, $get_module). Build the archives with:

    make -C ../vendor/qrcodegen TARGET=wasi
    make TARGET=wasi
"""

from typing import TYPE_CHECKING

import py.path

from spy.vm.bytes import W_Bytes
from spy.vm.primitive import W_I32, W_Bool
from spy.vm.registry import CModuleBuildInfo, ModuleRegistry
from spy.vm.str import W_Str

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

# The module name as seen by SPy code (`import qrcodegen`). It is *not*
# required to match the Python package name.
MODULE = ModuleRegistry("qrcodegen")

# Single combined archive (glue + vendored qrcodegen) built by the Makefile.
# Layout mirrors libspy/build/: build/<target>/spyvm_qrcodegen.a
_HERE = py.path.local(__file__).dirpath()
MODULE.wasm_archives = [
    _HERE.join("build", "wasi", "spyvm_qrcodegen.a"),
]

MODULE.build_info = CModuleBuildInfo(
    archive_specs=[(_HERE.join("build"), "spyvm_qrcodegen.a")],
    include_dirs=[_HERE.join("src"), _HERE.join("..", "vendor", "qrcodegen")],
    headers=[_HERE.join("src", "spyvm_qrcodegen.h")],
)


@MODULE.builtin_func
def w_encode(vm: "SPyVM", w_text: W_Str) -> W_Bytes:
    """
    Encode the given text into a QR Code, returning an opaque bytes object
    that can be passed to get_size() and get_module().
    """
    ptr = vm.ll.call("spy_qrcodegen$encode", w_text.ptr)
    return W_Bytes.from_ptr(vm, ptr)


@MODULE.builtin_func
def w_get_size(vm: "SPyVM", w_qr: W_Bytes) -> W_I32:
    """
    Return the side length of the QR Code (0 if encoding failed).
    """
    size = vm.ll.call("spy_qrcodegen$get_size", w_qr.ptr)
    return vm.wrap(size)


@MODULE.builtin_func
def w_get_module(vm: "SPyVM", w_qr: W_Bytes, w_x: W_I32, w_y: W_I32) -> W_Bool:
    """
    Return whether the module (pixel) at (x, y) is dark.
    """
    res = vm.ll.call("spy_qrcodegen$get_module", w_qr.ptr, w_x.value, w_y.value)
    return vm.wrap(bool(res))
