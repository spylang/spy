"""
A Python wrapper that abstracts the differences between wasmtime and emscripten.

It is called 'LL' for two reasons:

  - it exposes a low-level view on the code, compared to other wrappers which
    are more higher level (e.g., the concept of strings doesn't exist, we only
    have ints, floats and bytes of memory).

  - it's an unused prefix: other prefixes as "Py", "Wasm", "W" etc. would have
    been very confusing :)
"""
from spy.platform import IS_PYODIDE
from .base import HostModule, LLWasmType

if IS_PYODIDE:
    from .emscripten import LLWasmModule, LLWasmInstance, LLWasmMemory, WasmTrap
else:
    from .wasmtime import LLWasmModule, LLWasmInstance, LLWasmMemory, WasmTrap
