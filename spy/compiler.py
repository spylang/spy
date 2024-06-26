import os
from enum import Enum
import py.path
from spy.backend.c.cwriter import CModuleWriter
from spy.cbuild import ZigToolchain, ClangToolchain, EmscriptenToolchain
from spy.vm.vm import SPyVM
from spy.vm.module import W_Module

DUMP_C = False
DUMP_WASM = False

class ToolchainType(str, Enum):
    zig = "zig"
    clang = "clang"
    emscripten = "emscripten"
    native = "native"

class Compiler:
    """
    Take a module inside a VM and compile it to C/WASM.
    """
    vm: SPyVM
    w_mod: W_Module
    builddir: py.path.local
    file_c: py.path.local    # output file
    file_wasm: py.path.local # output file

    def __init__(self, vm: SPyVM, modname: str,
                 builddir: py.path.local) -> None:
        self.vm = vm
        self.w_mod = vm.modules_w[modname]
        basename = modname
        self.file_c = builddir.join(f'{basename}.c')
        self.file_wasm = builddir.join(f'{basename}.wasm')

    def cwrite(self) -> py.path.local:
        """
        Convert the W_Module into a .c file
        """
        file_spy = py.path.local(self.w_mod.filepath)
        self.cwriter = CModuleWriter(self.vm, self.w_mod, file_spy, self.file_c)
        self.cwriter.write_c_source()
        #
        if DUMP_C:
            print()
            print(f'---- {self.file_c} ----')
            print(self.file_c.read())
        #
        return self.file_c

    def cbuild(self, *,
               debug_symbols: bool = False,
               toolchain_type: ToolchainType = "zig",
               ) -> py.path.local:
        """
        Build the .c file into a .wasm file
        """
        file_c = self.cwrite()
        if toolchain_type == "zig":
            toolchain = ZigToolchain()
        elif toolchain_type == "clang":
            toolchain = ClangToolchain()
        elif toolchain_type == "emscripten":
            toolchain = EmscriptenToolchain()
        elif toolchain_type == "native":
            raise NotImplementedError("TODO")
        else:
            assert False
        exports = [fqn.c_name for fqn in self.w_mod.keys()]
        file_wasm = toolchain.c2wasm(file_c, self.file_wasm,
                                     exports=exports,
                                     debug_symbols=debug_symbols)
        #
        if DUMP_WASM:
            print()
            print(f'---- {self.file_wasm} ----')
            os.system(f'wasm2wat {file_wasm}')
        #
        return file_wasm
