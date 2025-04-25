import os
from enum import Enum
import py.path
from spy.backend.c.cwriter import CModuleWriter
from spy.cbuild import get_toolchain, BUILD_TYPE
from spy.build.ninja import NinjaWriter, BuildConfig
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
    build_dir: py.path.local
    outname: str
    dump_c: bool

    def __init__(
            self,
            vm: SPyVM,
            build_dir: py.path.local,
            *,
            outname: str,
            dump_c: bool
    ) -> None:
        self.vm = vm
        self.build_dir = build_dir
        self.outname = outname
        self.dump_c = dump_c

    def cwrite(self) -> py.path.local:
        """
        Convert all non-builtins modules into .c files
        """
        cfiles = []
        for modname, w_mod in self.vm.modules_w.items():
            if w_mod.is_builtin():
                continue

            file_spy = py.path.local(w_mod.filepath)
            basename = file_spy.purebasename
            file_c = self.build_dir.join(f'{basename}.c')
            cwriter = CModuleWriter(self.vm, w_mod, file_spy, file_c)
            cwriter.write_c_source()
            cfiles.append(file_c)
            #
            if self.dump_c:
                print()
                print(f'---- {file_c} ----')
                print(highlight_C_maybe(file_c.read()))
        return cfiles

    def build(self, config: BuildConfig) -> py.path.local:
        wasm_exports = []
        if config.target == 'wasi' and config.kind == 'lib':
            wasm_exports = self.get_wasm_exports()
        cfiles = self.cwrite()

        ninja = NinjaWriter(config, self.build_dir)
        ninja.write(self.outname, cfiles, wasm_exports=wasm_exports)
        outfile = ninja.build()
        if DUMP_WASM and outfile.ext == '.wasm':
            print()
            print(f'---- {outfile} ----')
            os.system(f'wasm2wat {outfile}')
        return outfile

    def get_wasm_exports(self) -> list[str]:
        # ok, this logic is wrong: we cannot know which names we want to
        # export by simply looking at their type: for example, in case of
        # variables we want to export "red variables" but we don't want to
        # export "blue variabes" (I guess?). For now, let's just include
        # red functions and integers
        wasm_exports = []
        for modname, w_mod in self.vm.modules_w.items():
            if w_mod.is_builtin():
                continue
            wasm_exports += [
                fqn.c_name
                for fqn, w_obj in w_mod.items_w()
                if (isinstance(w_obj, W_ASTFunc) and w_obj.color == 'red' or
                    isinstance(w_obj, W_I32))
            ]
        return wasm_exports
