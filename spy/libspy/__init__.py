"""
libspy: the C runtime of SPy.

This package must stay light to import (no wasmtime): the build hook imports
spy.libspy.builder. The runtime classes live in spy.libspy.host and are
loaded lazily, see __getattr__.
"""

import importlib
from typing import TYPE_CHECKING, Any

import py.path

import spy
from spy.build.flags import get_libdir
from spy.errors import SPyError
from spy.platform import IS_BROWSER, IS_DOCS_BUILD, IS_NODE, IS_PYODIDE

SRC = spy.ROOT.join("libspy", "src")
INCLUDE = spy.ROOT.join("libspy", "include")
BUILD = spy.ROOT.join("libspy", "build")
DEPS = spy.ROOT.join("libspy", "deps")
if TYPE_CHECKING:
    from spy.libspy.host import (  # noqa: F401
        BytesLayout,
        LibSPyHost,
        LLSPyInstance,
        StrLayout,
    )
    from spy.llwasm import LLWasmModule, WasmTrap  # noqa: F401


_LAZY = {
    "BytesLayout": "spy.libspy.host",
    "LibSPyHost": "spy.libspy.host",
    "LLSPyInstance": "spy.libspy.host",
    "StrLayout": "spy.libspy.host",
    "LLWasmModule": "spy.llwasm",
    "WasmTrap": "spy.llwasm",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        return getattr(importlib.import_module(_LAZY[name]), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Where to load libspy.wasm (or libspy.mjs) from. In the browser it needs to be
# set by the embedder; else it is computed on first use, so that importing
# spy never builds anything.
LIBSPY_WASM: Any = None
LLMOD: "LLWasmModule | None" = None


def _wasi_testlib() -> py.path.local:
    # the VM provides the debug helpers as WASM imports, so it always wants
    # the testlib flavor of libspy (e.g. wasi/debug-testlib)
    return py.path.local(get_libdir("wasi", "debug", "testlib"))


def _get_libspy_wasm() -> Any:
    if LIBSPY_WASM is not None:
        return LIBSPY_WASM
    if IS_NODE:
        return py.path.local(get_libdir("emscripten", "debug", "testlib")).join(
            "libspy.mjs"
        )
    if IS_BROWSER or IS_DOCS_BUILD:
        raise RuntimeError("libspy.LIBSPY_WASM needs to be set by the embedder")
    return _wasi_testlib().join("libspy.wasm")


# XXX is it correct to always use debug/libspy.wasm? For tests it's surely fine
# since we always compile them with SPY_DEBUG, but we need to double check
# what to do when we do e.g. spy build --release fine sine


def get_LLMOD(
    extra_archives: list[py.path.local] = [],
    *,
    force_rebuild: bool = False,
) -> "LLWasmModule":
    """
    Return a LLWasmModule for libspy, optionally bundled with extra .a archives.

    When extra_archives is empty, returns the (lazily created) LLMOD.
    When extra_archives is non-empty, links libspy.a + each extra archive into
    a single bundle (cached by content hash) and returns a LLWasmModule for it.
    """
    global LLMOD
    from spy.build.wasm_bundle import get_or_build_bundle
    from spy.llwasm import LLWasmModule

    if not extra_archives:
        assert not IS_PYODIDE
        if LLMOD is None:
            LLMOD = LLWasmModule(str(_get_libspy_wasm()))
        return LLMOD

    for archive in extra_archives:
        if not archive.check(file=True):
            raise SPyError(
                "W_ImportError",
                f"cannot find the archive '{archive}'.\n"
                f"Did you forget to build the spyvm extension module?",
            )

    libspy_a = _wasi_testlib().join("libspy.a")
    all_archives = [libspy_a] + list(extra_archives)
    bundle_path = get_or_build_bundle(all_archives, force_rebuild=force_rebuild)
    return LLWasmModule(str(bundle_path))


async def async_get_LLMOD() -> "LLWasmModule":
    global LLMOD
    from spy.llwasm import LLWasmModule

    if LLMOD is None:
        if IS_PYODIDE:
            LLMOD = await LLWasmModule.async_new(str(_get_libspy_wasm()))
        else:
            # wasmtime has no async constructor
            LLMOD = LLWasmModule(str(_get_libspy_wasm()))
    return LLMOD
