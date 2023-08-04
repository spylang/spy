import spy
from spy.llwasm import LLWasmModule, LLWasmInstance

INCLUDE = spy.ROOT.join('libspy', 'include')
LIBSPY_A = spy.ROOT.join('libspy', 'libspy.a')
LIBSPY_WASM = spy.ROOT.join('libspy', 'libspy.wasm')

MOD = LLWasmModule(LIBSPY_WASM)
