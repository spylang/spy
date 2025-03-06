"""
A Python wrapper that abstracts the differences between wasmtime and emscripten.

It is called 'LL' for two reasons:

  - it exposes a low-level view on the code, compared to other wrappers which
    are more higher level (e.g., the concept of strings doesn't exist, we only
    have ints, floats and bytes of memory).

  - it's an unused prefix: other prefixes as "Py", "Wasm", "W" etc. would have
    been very confusing :)
"""
from typing import TYPE_CHECKING
from spy.platform import IS_PYODIDE
from .base import HostModule, LLWasmType

# This is a bit of a hack: ideally, we would like mypy to understand that
# IS_PYODIDE is a "system platform check":
# https://mypy.readthedocs.io/en/stable/common_issues.html#python-version-and-system-platform-checks
#
# However, mypy doesn't know about IS_PYODIDE, evaluates both branches of the
# if and consider LLWasmModule&co. to be variables instead of type
# aliases. This causes problems a bit everywhere else.
#
# A quick hack is to use "not TYPE_CHECKING": this way, mypy only sees (and
# typechecks) the wasmtime path.
if not TYPE_CHECKING and IS_PYODIDE:
    from .emscripten import LLWasmModule, LLWasmInstance, LLWasmMemory, WasmTrap
else:
    from .wasmtime import LLWasmModule, LLWasmInstance, LLWasmMemory, WasmTrap
