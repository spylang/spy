"""
SPy out-of-tree builtin VM module wrapping the qrcodegen C library.

To be loaded via:
    spy --extra-vm-module ../spyvm_qrcodegen demo/main.spy

or by listing this package in the project's spy.toml:
    extra-vm-modules = ["../spyvm_qrcodegen"]

The package exposes a MODULE (ModuleRegistry) and a build_info callable.
The C half lives in src/spyvm_qrcodegen.c; it #includes libspy's public
headers and the vendored qrcodegen headers, and exposes three WASM exports
(spy_qrcodegen$encode, $get_size, $get_module). Build the archives with:

    make -C spyvm_qrcodegen
"""

from pathlib import Path
from typing import TYPE_CHECKING

from spy.build.build_info import BuildInfo, BuildTarget, BuildType
from spy.vm.bytes import W_Bytes
from spy.vm.primitive import W_I32, W_Bool
from spy.vm.registry import ModuleRegistry
from spy.vm.str import W_Str

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

MODULE = ModuleRegistry("qrcodegen")

HERE = Path(__file__).parent


def build_info(target: BuildTarget, build_type: BuildType) -> BuildInfo:
    return BuildInfo(
        include_dirs=[f"{HERE}/src", f"{HERE}/../vendor/qrcodegen"],
        headers=[f"{HERE}/src/spyvm_qrcodegen.h"],
        archives=[f"{HERE}/build/{target}/{build_type}/spyvm_qrcodegen.a"],
    )


@MODULE.builtin_func
def w_encode(vm: "SPyVM", w_text: W_Str) -> W_Bytes:
    ptr = vm.ll.call("spy_qrcodegen$encode", w_text.ptr)
    return W_Bytes.from_ptr(vm, ptr)


@MODULE.builtin_func
def w_get_size(vm: "SPyVM", w_qr: W_Bytes) -> W_I32:
    size = vm.ll.call("spy_qrcodegen$get_size", w_qr.ptr)
    return vm.wrap(size)


@MODULE.builtin_func
def w_get_module(vm: "SPyVM", w_qr: W_Bytes, w_x: W_I32, w_y: W_I32) -> W_Bool:
    res = vm.ll.call("spy_qrcodegen$get_module", w_qr.ptr, w_x.value, w_y.value)
    return vm.wrap(bool(res))
