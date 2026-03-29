from typing import Any, Optional

import spy
from spy.errors import SPyError
from spy.fqn import FQN
from spy.llwasm import HostModule, LLWasmInstance, LLWasmModule, WasmTrap
from spy.location import Loc
from spy.platform import IS_BROWSER, IS_NODE, IS_PYODIDE
from spy.vm.exc import FrameInfo, FrameKind, W_Traceback

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

    def _read_str(self, ptr: int) -> str:
        # ptr is const char*
        ba = self.ll.mem.read_cstr(ptr)
        return ba.decode("utf-8")

    # ========== WASM imports ==========

    def env_spy_debug_log(self, ptr: int) -> None:
        s = self._read_str(ptr)
        self.log.append(s)
        print("[log]", s)

    def env_spy_debug_log_i32(self, ptr: int, n: int) -> None:
        s = self._read_str(ptr)
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
        self.panic_etype = self._read_str(ptr_etype)
        self.panic_message = self._read_str(ptr_msg)
        self.panic_filename = self._read_str(ptr_fname)
        self.panic_lineno = lineno


class CFrameInfo(FrameInfo):
    """
    A FrameInfo built from data recorded in SPY_exc.frames[] by the C backend.

    FrameInfo normally requires a live AbstractFrame object, but for the C
    backend we only have the raw (fqn, loc) data extracted from WASM memory.
    """

    _fqn: FQN
    loc: Loc  # shadows the instance attr set by FrameInfo.__init__

    def __init__(self, fqn: FQN, loc: Loc) -> None:
        # Deliberately bypass FrameInfo.__init__ — no spyframe available.
        self._fqn = fqn
        self.loc = loc

    @property
    def kind(self) -> FrameKind:
        return "astframe"

    @property
    def fqn(self) -> FQN:
        return self._fqn


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

    def call(self, name: str, *args: Any) -> Any:
        try:
            result = super().call(name, *args)
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

        # Check for non-aborting exceptions set via spy_exc_set().
        # We use super().call() to bypass this wrapper and avoid recursion.
        etype_ptr = super().call("spy_exc_get_etype")
        if etype_ptr:
            msg_ptr = super().call("spy_exc_get_message")
            fname_ptr = super().call("spy_exc_get_fname")
            lineno = super().call("spy_exc_get_lineno")
            etype = self.mem.read_cstr(etype_ptr).decode("utf-8")
            message = self.mem.read_cstr(msg_ptr).decode("utf-8") if msg_ptr else ""
            fname = (
                self.mem.read_cstr(fname_ptr).decode("utf-8")
                if fname_ptr
                else "<unknown>"
            )
            # Read traceback frames (pushed innermost-first, reverse for display).
            nframes = super().call("spy_exc_get_nframes")
            frame_entries: list[FrameInfo] = []
            for i in range(nframes):
                fqn_ptr = super().call("spy_exc_get_frame_fqn", i)
                filename_ptr = super().call("spy_exc_get_frame_filename", i)
                line = super().call("spy_exc_get_frame_line", i)
                col_start = super().call("spy_exc_get_frame_col_start", i)
                col_end = super().call("spy_exc_get_frame_col_end", i)
                fqn_str = self.mem.read_cstr(fqn_ptr).decode("utf-8")
                file_str = self.mem.read_cstr(filename_ptr).decode("utf-8")
                frame_loc = Loc(file_str, line, line, col_start, col_end)
                frame_entries.append(CFrameInfo(FQN(fqn_str), frame_loc))
            frame_entries.reverse()
            super().call("spy_exc_clear")
            loc = Loc(fname, lineno, lineno, 1, -1)
            err = SPyError.simple("W_" + etype, message, "", loc)
            if frame_entries:
                err.w_exc.w_tb = W_Traceback(frame_entries)
            raise err

        return result
