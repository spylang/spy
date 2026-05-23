from dataclasses import dataclass
from typing import Any, Optional

import spy
from spy.errors import SPyError
from spy.llwasm import HostModule, LLWasmInstance, LLWasmModule, WasmTrap
from spy.location import Loc
from spy.platform import IS_BROWSER, IS_NODE, IS_PYODIDE

SRC = spy.ROOT.join("libspy", "src")
INCLUDE = spy.ROOT.join("libspy", "include")
BUILD = spy.ROOT.join("libspy", "build")
DEPS = spy.ROOT.join("libspy", "deps")


if IS_NODE:
    LIBSPY_WASM = BUILD.join("emscripten", "debug", "libspy.mjs")
    LLMOD = None
elif IS_BROWSER:
    LIBSPY_WASM = None  # type: ignore    # needs to be set by the embedder
    LLMOD = None
else:
    assert not IS_PYODIDE
    # "normal" python, we can preload LLMOD
    LIBSPY_WASM = BUILD.join("wasi", "debug", "libspy.wasm")
    LLMOD = LLWasmModule(LIBSPY_WASM)  # type: ignore

# XXX ^^^^
# is it correct to always use debug/libspy.wasm? For tests it's surely fine
# since we always compile them with SPY_DEBUG, but we need to double check
# what to do when we do e.g. spy build --release fine sine


async def async_get_LLMOD() -> LLWasmModule:
    global LLMOD
    if LLMOD is None:
        LLMOD = await LLWasmModule.async_new(str(LIBSPY_WASM))
    return LLMOD


class LibSPyHost(HostModule):
    log: list[str]
    panic_message: Optional[str]
    panic_filename: Optional[str]
    panic_lineno: int

    def __init__(self) -> None:
        self.log = []
        self.panic_message = None
        self.panic_filename = None
        self.panic_lineno = 0

    def _read_cstr(self, ptr: int) -> str:
        # ptr is const char*
        ba = self.ll.mem.read_cstr(ptr)
        return ba.decode("utf-8")

    # ========== WASM imports ==========

    def env_spy_debug_log(self, ptr: int) -> None:
        s = self._read_cstr(ptr)
        self.log.append(s)
        print("[log]", s)

    def env_spy_debug_log_i32(self, ptr: int, n: int) -> None:
        s = self._read_cstr(ptr)
        msg = f"{s} {n}"
        self.log.append(msg)
        print("[log]", msg)

    def env_spy_debug_set_panic_message(
        self, ptr_etype: int, ptr_msg: int, ptr_fname: int, lineno: int
    ) -> None:
        # ptr_* are const char*
        assert ptr_etype != 0
        assert ptr_msg != 0
        assert ptr_fname != 0
        self.panic_etype = self._read_cstr(ptr_etype)
        self.panic_message = self._read_cstr(ptr_msg)
        self.panic_filename = self._read_cstr(ptr_fname)
        self.panic_lineno = lineno


@dataclass
class StrLayout:
    # See also the struct _spy_StrObject_layout in str.h
    size: int
    length_offset: int
    hash_offset: int
    utf8_offset: int


class LLSPyInstance(LLWasmInstance):
    """
    A specialized version of LLWasmInstance which automatically link against
    LibSPyHost()
    """

    def __init__(
        self,
        llmod: LLWasmModule,
        hostmods: list[HostModule] = [],
        *,
        instance: Any = None,
    ) -> None:
        self.libspy = LibSPyHost()
        hostmods = [self.libspy] + hostmods
        super().__init__(llmod, hostmods, instance=instance)
        layout = self.call("_spy_StrObject_layout")
        self.str_layout = StrLayout(*layout)

    def read_str(self, ptr: int) -> tuple[int, int, bytes]:
        """
        Read a spy_StrObject at ptr from linear memory.
        Returns (length, hash, utf8_bytes).
        """
        layout = self.str_layout
        length = self.mem.read_i32(ptr + layout.length_offset)
        hash_ = self.mem.read_i32(ptr + layout.hash_offset)
        utf8_ptr = self.mem.read_i32(ptr + layout.utf8_offset)
        utf8 = bytes(self.mem.read(utf8_ptr, length))
        return length, hash_, utf8

    def call(self, name: str, *args: Any) -> Any:
        try:
            return super().call(name, *args)
        except WasmTrap:
            if self.libspy.panic_message is not None:
                assert self.libspy.panic_filename is not None
                etype = "W_" + self.libspy.panic_etype
                message = self.libspy.panic_message
                fname = self.libspy.panic_filename
                lineno = self.libspy.panic_lineno
                loc = Loc(fname, lineno, lineno, 1, -1)
                raise SPyError.simple(etype, message, "", loc)
            raise
