from dataclasses import dataclass
from typing import Optional

import py.path

from spy.backend.c.cffiwriter import CFFIWriter
from spy.backend.c.context import C_Type, Context
from spy.fqn import FQN
from spy.textbuilder import TextBuilder
from spy.vm.modules.types import W_LiftedType
from spy.vm.modules.unsafe.ptr import W_PtrType
from spy.vm.object import W_Type
from spy.vm.struct import W_StructType
from spy.vm.vm import SPyVM


@dataclass
class CStructDefs:
    hfile: py.path.local
    content: list[tuple[FQN, W_Type]]


class CStructWriter:
    ctx: Context
    c_structdefs: CStructDefs

    # main and nested TextBuilders for _types.h
    tbh: TextBuilder
    tbh_includes: TextBuilder  # XXX kill
    tbh_fwdecl: TextBuilder  # forward type declarations
    tbh_structs: TextBuilder  # type definitions
    tbh_ptrs_def: TextBuilder  # ptr and typelift accessors

    def __init__(
        self,
        vm: SPyVM,
        c_structdefs: CStructDefs,
        cffi: CFFIWriter,
    ) -> None:
        self.ctx = Context(vm)
        self.c_structdefs = c_structdefs
        self.cffi = cffi
        self.tbh = TextBuilder(use_colors=False)
        self.init_h()

    def __repr__(self) -> str:
        return f"<CStructWriter for {self.c_structdefs.hfile}>"

    def write_c_source(self) -> None:
        """
        Write the structdefs header
        """
        self.emit_content()
        self.c_structdefs.hfile.write(self.tbh.build())

    def init_h(self) -> None:
        GUARD = self.c_structdefs.hfile.purebasename.upper()
        self.tbh.wb(f"""
        #ifndef SPY_{GUARD}_H
        #define SPY_{GUARD}_H

        #include <spy.h>

        #ifdef __cplusplus
        extern "C" {{
        #endif
        """)
        self.tbh.wl()

        self.tbh.wl("// includes")
        self.tbh_includes = self.tbh.make_nested_builder()
        self.tbh.wl()

        self.tbh.wl("// forward type declarations")
        self.tbh_fwdecl = self.tbh.make_nested_builder()
        self.tbh.wl()

        self.tbh.wl("// struct definitions")
        self.tbh_structs = self.tbh.make_nested_builder()
        self.tbh.wl()

        self.tbh.wl("// ptr and typelift accessors")
        self.tbh_ptrs_def = self.tbh.make_nested_builder()
        self.tbh.wl()

        self.ctx.tbh_includes = self.tbh_includes

        self.tbh.wl()
        self.tbh.wb("""
        #ifdef __cplusplus
        }  // extern "C"
        #endif

        #endif  // Header guard
        """)

    def emit_content(self) -> None:
        for fqn, w_type in self.c_structdefs.content:
            assert fqn == w_type.fqn  # sanity check
            if isinstance(w_type, W_StructType):
                self.emit_StructType(fqn, w_type)
            elif isinstance(w_type, W_PtrType):
                self.emit_PtrType(fqn, w_type)
            elif isinstance(w_type, W_LiftedType):
                self.emit_LiftedType(fqn, w_type)
            else:
                assert False, f"Unknown type: {w_type}"

    def emit_StructType(self, fqn: FQN, w_st: W_StructType) -> None:
        c_st = C_Type(w_st.fqn.c_name)
        self.tbh_fwdecl.wl(f"typedef struct {c_st} {c_st}; /* {w_st.fqn.human_name} */")
        # XXX this is VERY wrong: it assumes that the standard C layout
        # matches the layout computed by struct.calc_layout: as long as we use
        # only 32-bit types it should work, but eventually we need to do it
        # properly.
        tb = self.tbh_structs
        tb.wl("struct %s {" % c_st)
        with tb.indent():
            for name, w_field in w_st.fields_w.items():
                c_fieldtype = self.ctx.w2c(w_field.w_T)
                tb.wl(f"{c_fieldtype} {name};")
        tb.wl("};")
        tb.wl("")

    def emit_PtrType(self, fqn: FQN, w_ptrtype: W_PtrType) -> None:
        c_ptrtype = C_Type(w_ptrtype.fqn.c_name)
        w_itemtype = w_ptrtype.w_itemtype
        c_itemtype = self.ctx.w2c(w_itemtype)
        self.tbh_fwdecl.wb(f"""
        typedef struct {c_ptrtype} {{
            {c_itemtype} *p;
        #ifdef SPY_DEBUG
            size_t length;
        #endif
        }} {c_ptrtype};
        """)
        self.tbh_fwdecl.wl()

        self.tbh_ptrs_def.wb(f"""
        SPY_PTR_FUNCTIONS({c_ptrtype}, {c_itemtype});
        #define {c_ptrtype}$NULL (({c_ptrtype}){{0}})
        """)
        self.tbh_ptrs_def.wl()

    def emit_LiftedType(self, fqn: FQN, w_hltype: W_LiftedType) -> None:
        c_hltype = C_Type(w_hltype.fqn.c_name)
        w_lltype = w_hltype.w_lltype
        c_lltype = self.ctx.w2c(w_lltype)
        self.tbh_fwdecl.wl(
            f"typedef struct {c_hltype} {c_hltype}; /* {w_hltype.fqn.human_name} */"
        )
        self.tbh_structs.wb(f"""
        typedef struct {c_hltype} {{
            {c_lltype} ll;
        }} {c_hltype};
        """)
        self.tbh_structs.wl()

        self.tbh_ptrs_def.wb(f"""
        SPY_TYPELIFT_FUNCTIONS({c_hltype}, {c_lltype});
        """)
        self.tbh_ptrs_def.wl()
