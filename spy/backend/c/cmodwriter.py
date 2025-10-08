import itertools
from dataclasses import dataclass
from typing import Iterable, Optional

import py.path

from spy.backend.c.cffiwriter import CFFIWriter
from spy.backend.c.context import C_Type, Context
from spy.backend.c.cwriter import CFuncWriter
from spy.fqn import FQN
from spy.textbuilder import TextBuilder
from spy.vm.cell import W_Cell
from spy.vm.function import W_ASTFunc, W_BuiltinFunc
from spy.vm.module import W_Module
from spy.vm.modules.types import W_LiftedType
from spy.vm.modules.unsafe.ptr import W_Ptr, W_PtrType
from spy.vm.object import W_Object, W_Type
from spy.vm.primitive import W_I32
from spy.vm.struct import W_StructType
from spy.vm.vm import SPyVM



@dataclass
class CModule:
    modname: str
    spyfile: py.path.local
    hfile: py.path.local
    cfile: py.path.local
    content: list[tuple[FQN, W_Object]]

    def __repr__(self) -> str:
        return f"<CModule {self.modname}>"


class CModuleWriter:
    ctx: Context
    c_mod: CModule
    global_vars: set[str]
    jsffi_error_emitted: bool = False

    # main and nested TextBuilders for .h (non-type content)
    tbh: TextBuilder
    tbh_warnings: TextBuilder
    tbh_includes: TextBuilder  # includes for other modules
    tbh_funcs: TextBuilder  # function declarations
    tbh_globals: TextBuilder  # global var declarations (.h)

    # main and nested TextBuilders for .c
    tbc: TextBuilder
    tbc_funcs: TextBuilder  # functions
    tbc_globals: TextBuilder  # global var definition (.c)

    def __init__(
        self,
        vm: SPyVM,
        c_mod: CModule,
        cffi: CFFIWriter,
    ) -> None:
        self.ctx = Context(vm)
        self.c_mod = c_mod
        self.cffi = cffi
        self.tbh = TextBuilder(use_colors=False)
        self.tbc = TextBuilder(use_colors=False)
        # nested builders are initialized lazily
        self.global_vars = set()
        self.init_h()
        self.init_c()

    def __repr__(self) -> str:
        return f"<CModuleWriter for {self.c_mod.modname}>"

    def write_c_source(self) -> None:
        self.emit_content()
        self.c_mod.hfile.write(self.tbh.build())
        self.c_mod.cfile.write(self.tbc.build())

    def new_global_var(self, prefix: str) -> str:
        """
        Create an unique name for a global var whose name starts with 'prefix'
        """
        prefix = f"SPY_g_{prefix}"
        for i in itertools.count():
            varname = f"{prefix}{i}"
            if varname not in self.global_vars:
                break
        self.global_vars.add(varname)
        return varname

    def init_h(self) -> None:
        GUARD = self.c_mod.hfile.purebasename.upper()
        self.tbh.wb(f"""
        #ifndef SPY_{GUARD}_H
        #define SPY_{GUARD}_H

        #include <spy.h>

        #ifdef __cplusplus
        extern "C" {{
        #endif
        """)
        self.tbh.wl()
        self.tbh_warnings = self.tbh.make_nested_builder()
        self.tbh.wl()

        self.tbh.wl("// includes")
        self.tbh.wl('#include "spy_structdefs.h"')
        self.tbh_includes = self.tbh.make_nested_builder()
        self.tbh.wl()

        self.tbh.wl("// function declarations")
        self.tbh_funcs = self.tbh.make_nested_builder()
        self.tbh.wl()

        self.tbh.wl("// global variable declarations")
        self.tbh_globals = self.tbh.make_nested_builder()
        self.tbh.wl()

        self.ctx.tbh_includes = self.tbh_includes

        self.tbh.wl()
        self.tbh.wb("""
        #ifdef __cplusplus
        }  // extern "C"
        #endif

        #endif  // Header guard
        """)

    def init_c(self) -> None:
        header_name = self.c_mod.hfile.basename
        self.cffi.emit_include(header_name)
        self.tbc.wb(f"""
        #include "{header_name}"
        """)
        if self.c_mod.spyfile is not None:
            self.tbc.wb(f"""
            #ifdef SPY_DEBUG_C
            #    define SPY_LINE(SPY, C) C "{self.c_mod.cfile}"
            #else
            #    define SPY_LINE(SPY, C) SPY "{self.c_mod.spyfile}"
            #endif
            """)
        self.tbc.wl()
        self.tbc.wl("// constants and globals")
        self.tbc_globals = self.tbc.make_nested_builder()
        self.tbc.wl()
        self.tbc.wl("// content of the module")
        self.tbc.wl()
        self.tbc_content = self.tbc.make_nested_builder()

        # Main function
        fqn_main = FQN([self.c_mod.modname, "main"])
        if fqn_main in self.ctx.vm.globals_w:
            self.tbc.wb(f"""
                int main(void) {{
                    {fqn_main.c_name}();
                    return 0;
                }}
            """)

    def emit_jsffi_error_maybe(self) -> None:
        if self.jsffi_error_emitted:
            return
        self.tbh_warnings.wb("""
        #ifndef SPY_TARGET_EMSCRIPTEN
        #  error "jsffi is available only for emscripten targets"
        #endif
        """)
        self.jsffi_error_emitted = True

    def emit_content(self) -> None:
        for fqn, w_obj in self.c_mod.content:
            assert w_obj is not None, "uninitialized global?"
            self.emit_obj(fqn, w_obj)

    def emit_obj(self, fqn: FQN, w_obj: W_Object) -> None:
        if hasattr(w_obj, "fqn"):
            assert fqn == w_obj.fqn  # sanity check

        w_T = self.ctx.vm.dynamic_type(w_obj)

        # ==== functions ====
        if isinstance(w_obj, W_ASTFunc):
            # emit red functions, ignore blue ones
            if w_obj.color == "red":
                self.emit_func(fqn, w_obj)

        elif isinstance(w_obj, W_BuiltinFunc):
            # ignore builtin functions
            pass

        # ==== global variables (cells) ====
        elif isinstance(w_obj, W_Cell):
            w_content = w_obj.get()
            w_T = self.ctx.vm.dynamic_type(w_content)
            # we support only int global variables for now
            assert isinstance(w_content, W_I32), "WIP: var type not supported"
            intval = self.ctx.vm.unwrap(w_content)
            c_type = self.ctx.w2c(w_T)
            self.tbh_globals.wl(f"extern {c_type} {fqn.c_name};")
            self.tbc_globals.wl(f"{c_type} {fqn.c_name} = {intval};")

        # ==== misc consts ====
        elif isinstance(w_T, W_PtrType):
            # for now, we only support NULL constnts
            assert isinstance(w_obj, W_Ptr)
            assert w_obj.addr == 0, (
                "only NULL pointers can be stored in constants for now"
            )
            c_type = self.ctx.w2c(w_T)
            self.tbh_globals.wl(f"extern {c_type} {fqn.c_name};")
            self.tbc_globals.wl(f"{c_type} {fqn.c_name} = {{0}};")

        else:
            raise NotImplementedError("WIP")

    def emit_func(self, fqn: FQN, w_func: W_ASTFunc) -> None:
        # func prototype in .h
        c_func = self.ctx.c_function(fqn.c_name, w_func)
        self.tbh_funcs.wl(c_func.decl() + ";")

        # func body in .c
        fw = CFuncWriter(self.ctx, self, fqn, w_func)
        fw.emit()

        # cffi wrapper
        self.cffi.emit_func(self.ctx, fqn, w_func)
