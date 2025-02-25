import sys
from typing import Any, Optional
import spy
from spy.llwasm import LLWasmModule, LLWasmInstance, HostModule, WasmTrap
from spy.platform import IS_BROWSER, IS_NODE, IS_PYODIDE
#from spy.vm.str import ll_spy_Str_read

SRC = spy.ROOT.join('libspy', 'src')
INCLUDE = spy.ROOT.join('libspy', 'include')
BUILD = spy.ROOT.join('libspy', 'build')



if IS_NODE:
    LIBSPY_WASM = BUILD.join('emscripten', 'debug', 'libspy.mjs')
    LLMOD = None
elif IS_BROWSER:
    LIBSPY_WASM = None  # needs to be set by the embedder
    LLMOD = None
else:
    assert not IS_PYODIDE
    # "normal" python, we can preload LLMOD
    LIBSPY_WASM = BUILD.join('wasi', 'debug', 'libspy.wasm')
    LLMOD = LLWasmModule(LIBSPY_WASM)

# XXX ^^^^
# is it correct to always use debug/libspy.wasm? For tests it's surely fine
# since we always compile them with SPY_DEBUG, but we need to double check
# what to do when we do e.g. spy -c --release fine sine


async def async_get_LLMOD():
    global LLMOD
    if LLMOD is None:
        LLMOD = await LLWasmModule.async_new(LIBSPY_WASM)
    return LLMOD


class LibSPyHost(HostModule):
    log: list[str]
    panic_message: Optional[str]

    def __init__(self) -> None:
        self.log = []
        self.panic_message = None

    def _read_str(self, ptr: int) -> str:
        # ptr is const char*
        ba = self.ll.mem.read_cstr(ptr)
        return ba.decode('utf-8')

    # ========== WASM imports ==========

    def env_spy_debug_log(self, ptr: int) -> None:
        s = self._read_str(ptr)
        self.log.append(s)
        print('[log]', s)

    def env_spy_debug_log_i32(self, ptr: int, n: int) -> None:
        s = self._read_str(ptr)
        msg = f'{s} {n}'
        self.log.append(msg)
        print('[log]', msg)

    def env_spy_debug_set_panic_message(self, ptr: int) -> None:
        # ptr is const char*
        ba = self.ll.mem.read_cstr(ptr)
        self.panic_message = ba.decode('utf-8')


class SPyPanicError(Exception):
    """
    Python-level exception raised when a WASM module aborts with a call to
    spy_panic().
    """


class LLSPyInstance(LLWasmInstance):
    """
    A specialized version of LLWasmInstance which automatically link against
    LibSPyHost()
    """

    def __init__(self, llmod: LLWasmModule,
                 hostmods: list[HostModule]=[], *, instance=None) -> None:
        self.libspy = LibSPyHost()
        hostmods = [self.libspy] + hostmods
        super().__init__(llmod, hostmods, instance=instance)

    def call(self, name: str, *args: Any) -> Any:
        try:
            return super().call(name, *args)
        except WasmTrap:
            if self.libspy.panic_message is not None:
                raise SPyPanicError(self.libspy.panic_message)
            raise
