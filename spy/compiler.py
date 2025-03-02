import os
from enum import Enum
import py.path
from spy.backend.c.cwriter import CModuleWriter
from spy.cbuild import get_toolchain, BUILD_TYPE
from spy.vm.vm import SPyVM
from spy.vm.module import W_Module
from spy.vm.function import W_ASTFunc
from spy.vm.primitive import W_I32
from spy.util import highlight_C_maybe

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
                 builddir: py.path.local,
                 *,
                 dump_c: bool) -> None:
        self.vm = vm
        self.dump_c = dump_c
        self.w_mod = vm.modules_w[modname]
        basename = modname
        self.builddir = builddir
        self.file_c = builddir.join(f'{basename}.c')
        self.file_wasm = builddir.join(f'{basename}.wasm')

    def cwrite(self, target: str) -> py.path.local:
        """
        Convert the W_Module into a .c file
        """
        file_spy = py.path.local(self.w_mod.filepath)
        self.cwriter = CModuleWriter(self.vm, self.w_mod, file_spy, self.file_c,
                                     target)
        self.cwriter.write_c_source()
        #
        if self.dump_c:
            print()
            print(f'---- {self.file_c} ----')
            print(highlight_C_maybe(self.file_c.read()))
        #
        return self.file_c

    def cbuild(self, *,
               opt_level: int,
               debug_symbols: bool,
               release_mode: bool,
               toolchain_type: ToolchainType,
               ) -> py.path.local:
        """
        Build the .c file into a .wasm file or an executable
        """
        build_type: BUILD_TYPE = 'release' if release_mode else 'debug'
        toolchain = get_toolchain(toolchain_type, build_type=build_type)
        file_c = self.cwrite(toolchain.TARGET)
        if toolchain.TARGET == 'wasi':
            # ok, this logic is wrong: we cannot know which names we want to
            # export by simply looking at their type: for example, in case of
            # variables we want to export "red variables" but we don't want to
            # export "blue variabes" (I guess?). For now, let's just include
            # red functions and integers
            exports = [
                fqn.c_name
                for fqn, w_obj in self.w_mod.items_w()
                if (isinstance(w_obj, W_ASTFunc) and w_obj.color == 'red' or
                    isinstance(w_obj, W_I32))
            ]
            file_wasm = toolchain.c2wasm(file_c, self.builddir,
                                         exports=exports,
                                         opt_level=opt_level,
                                         debug_symbols=debug_symbols)
            assert file_wasm == self.file_wasm
            if DUMP_WASM:
                print()
                print(f'---- {self.file_wasm} ----')
                os.system(f'wasm2wat {file_wasm}')
            return file_wasm
        else:
            file_exe = self.file_wasm.new(ext=toolchain.EXE_FILENAME_EXT)
            toolchain.c2exe(file_c, file_exe,
                            opt_level=opt_level,
                            debug_symbols=debug_symbols)
            return file_exe
