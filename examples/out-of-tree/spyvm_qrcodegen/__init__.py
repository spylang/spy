"""
SPy out-of-tree builtin VM module wrapping the qrcodegen C library.

To be loaded via:
    spy --extra-vm-module ../spyvm_qrcodegen demo/main.spy

or by listing this package in the project's spy.toml:
    extra-vm-modules = ["../spyvm_qrcodegen"]

The package exposes a single name `MODULE` which is an instance of
ModuleRegistry. The SPy CLI imports this package and reads `MODULE` to
discover the module's name, contents, and C-build metadata.
"""

import py.path

from spy.vm.registry import ModuleRegistry

# The module name as seen by SPy code (`import qrcodegen`). It is *not*
# required to match the Python package name.
MODULE = ModuleRegistry("qrcodegen")

# Path to the pre-built WASI archive for this module. When SPy loads this
# module in interpreted (WASM) mode it bundles this archive together with
# libspy.a into a single reactor .wasm. Must be built before loading.
_HERE = py.path.local(__file__).dirpath()
MODULE.wasm_archive = _HERE.join(
    "..", "vendor", "qrcodegen", "build", "wasi", "libqrcodegen.a"
)

# TODO: declare the actual bindings: qrcodegen_encodeText, qrcodegen_getSize,
# qrcodegen_getModule. Probably modeled on spy/vm/modules/math.py.
