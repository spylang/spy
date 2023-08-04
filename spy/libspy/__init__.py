import spy
from spy.llwasm import LLWasmModule, LLWasmInstance, HostModule
#from spy.vm.str import ll_spy_Str_read

INCLUDE = spy.ROOT.join('libspy', 'include')
LIBSPY_A = spy.ROOT.join('libspy', 'libspy.a')
LIBSPY_WASM = spy.ROOT.join('libspy', 'libspy.wasm')

LLMOD = LLWasmModule(LIBSPY_WASM)

class LibSPyHost(HostModule):
    log: list[str]

    def __init__(self) -> None:
        self.log = []

    # ========== WASM imports ==========

    def env_spy_debug_log(self, ptr: int) -> None:
        # ptr is const char*
        ba = self.ll.mem.read_cstr(ptr)
        s = ba.decode('utf-8')
        self.log.append(s)
        print('[log]', s)
