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

from spy.vm.registry import ModuleRegistry

# The module name as seen by SPy code (`import qrcodegen`). It is *not*
# required to match the Python package name.
MODULE = ModuleRegistry("qrcodegen")

# C-build metadata. Consumed by the C backend when compiling SPy code that
# imports this module. Path placeholders:
#   ${ORIGIN}  - the directory containing this package
#   ${TARGET}  - the build target (native, native-static, wasi, emscripten)
#
# TODO: build_info is not yet implemented on ModuleRegistry; the exact
# attribute shape is still TBD. The assignments below are a sketch.
MODULE.build_info.include_dirs = ["${ORIGIN}/../vendor/qrcodegen"]
MODULE.build_info.library_dirs = ["${ORIGIN}/../vendor/qrcodegen/build/${TARGET}"]
MODULE.build_info.libraries = ["qrcodegen"]
MODULE.build_info.cflags = []

# TODO: declare the actual bindings: qrcodegen_encodeText, qrcodegen_getSize,
# qrcodegen_getModule. Probably modeled on spy/vm/modules/math.py.
