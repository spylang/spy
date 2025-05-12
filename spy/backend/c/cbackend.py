from typing import Optional
import os
from enum import Enum
import py.path
from spy.backend.c.cmodwriter import CModuleWriter
from spy.backend.c.cffiwriter import CFFIWriter
from spy.build.config import BuildConfig
from spy.build.ninja import NinjaWriter
from spy.build.cffi import cffi_build
from spy.vm.vm import SPyVM
from spy.vm.object import W_Object
from spy.vm.module import W_Module, ModItem
from spy.vm.function import W_ASTFunc
from spy.vm.primitive import W_I32
from spy.vm.modules.unsafe.ptr import W_PtrType
from spy.util import highlight_C_maybe

class CBackend:
    """
    Convert SPy modules into C files
    """
    vm: SPyVM
    outname: str
    config: BuildConfig
    build_dir: py.path.local
    dump_c: bool
    cffi: CFFIWriter
    ninja: Optional[NinjaWriter]
    cfiles: list[py.path.local]
    build_script: Optional[py.path.local]

    def __init__(
            self,
            vm: SPyVM,
            outname: str,
            config: BuildConfig,
            build_dir: py.path.local,
            *,
            dump_c: bool
    ) -> None:
        self.vm = vm
        self.outname = outname
        self.config = config
        self.build_dir = build_dir
        self.build_dir.join('src').ensure(dir=True)
        self.dump_c = dump_c
        #
        self.cffi = CFFIWriter(outname, config, build_dir)
        self.ninja = None
        self.cfiles = [] # generated C files
        self.build_script = None

    def cwrite(self) -> None:
        """
        Convert all non-builtins modules into .c files
        """
        self.cwrite_builtins_extra()
        for modname, w_mod in self.vm.modules_w.items():
            if w_mod.is_builtin():
                continue
            assert w_mod.filepath is not None
            file_spy = py.path.local(w_mod.filepath)
            basename = file_spy.purebasename
            file_c = self.build_dir.join('src', f'{basename}.c')
            file_h = self.build_dir.join('src', f'{basename}.h')
            cwriter = CModuleWriter(
                self.vm, w_mod, file_spy, file_h, file_c,
                self.cffi,
            )
            cwriter.write_c_source()
            self.cfiles.append(file_c)
            #
            if self.dump_c:
                print()
                print(f'---- {file_c} ----')
                print(highlight_C_maybe(file_c.read()))


    def cwrite_builtins_extra(self) -> None:
        # find all the unsafe::ptr to a builtin
        def is_ptr_to_builtin(w_obj: W_Object) -> bool:
            return (
                isinstance(w_obj, W_PtrType) and
                w_obj.w_itemtype.fqn.modname == 'builtins'
            )
        mod_items = [
            (fqn, w_obj)
            for fqn, w_obj in self.vm.globals_w.items()
            if is_ptr_to_builtin(w_obj)
        ]

        w_mod = self.vm.modules_w['builtins']
        file_h = self.build_dir.join('src', 'builtins_extra.h')
        cwriter = CModuleWriter(
            self.vm, w_mod, None, file_h, None, self.cffi,
            mod_items=mod_items
        )
        cwriter.write_c_source()

    def write_build_script(self) -> None:
        assert self.cfiles != [], 'call .cwrite() first'
        wasm_exports = []
        if self.config.target == 'wasi' and self.config.kind == 'lib':
            wasm_exports = self.get_wasm_exports()

        if self.config.kind == 'py-cffi':
            assert wasm_exports == []
            self.build_script = self.cffi.write(self.cfiles)
        else:
            self.ninja = NinjaWriter(self.config, self.build_dir)
            self.ninja.write(self.outname, self.cfiles,
                             wasm_exports=wasm_exports)
            self.build_script = self.build_dir.join('build.ninja')


    def build(self) -> py.path.local:
        if self.config.kind == 'py-cffi':
            assert self.build_script is not None
            return cffi_build(self.build_script)
        else:
            assert self.ninja is not None
            return self.ninja.build()


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
