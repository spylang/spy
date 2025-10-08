from typing import Optional
from dataclasses import dataclass
import py.path
from spy.fqn import FQN
from spy.vm.object import W_Type
from spy.vm.struct import W_StructType
from spy.vm.modules.types import W_LiftedType
from spy.vm.modules.unsafe.ptr import W_PtrType
from spy.textbuilder import TextBuilder
from spy.backend.c.context import Context, C_Type


@dataclass
class CTypesDefs:
    hfile: py.path.local
    types: list[tuple[FQN, W_Type]]


class CTypesWriter:
    ctx: Context
    c_types: CTypesDefs

    # main and nested TextBuilders for _types.h
    tbh_types: TextBuilder
    tbh_types_includes: TextBuilder
    tbh_types_decl: TextBuilder  # forward type declarations
    tbh_types_def: TextBuilder   # type definitions
    tbh_ptrs_def: TextBuilder    # ptr and typelift accessors

    def __init__(self, ctx: Context, c_types: CTypesDefs) -> None:
        self.ctx = ctx
        self.c_types = c_types
        self.tbh_types = TextBuilder(use_colors=False)
        self.init_h_types()

    def __repr__(self) -> str:
        return f'<CTypesWriter for {self.c_types.hfile}>'

    def write_types_header(self) -> None:
        """
        Write the types header file
        """
        self.emit_types()
        self.c_types.hfile.write(self.tbh_types.build())

    def init_h_types(self) -> None:
        GUARD = self.c_types.hfile.purebasename.upper()
        self.tbh_types.wb(f"""
        #ifndef SPY_{GUARD}_H
        #define SPY_{GUARD}_H

        #include <spy.h>

        #ifdef __cplusplus
        extern "C" {{
        #endif
        """)
        self.tbh_types.wl()

        self.tbh_types.wl('// includes')
        self.tbh_types_includes = self.tbh_types.make_nested_builder()
        self.tbh_types.wl()

        self.tbh_types.wl('// forward type declarations')
        self.tbh_types_decl = self.tbh_types.make_nested_builder()
        self.tbh_types.wl()

        self.tbh_types.wl('// type definitions')
        self.tbh_types_def = self.tbh_types.make_nested_builder()
        self.tbh_types.wl()

        self.tbh_types.wl('// ptr and typelift accessors')
        self.tbh_ptrs_def = self.tbh_types.make_nested_builder()
        self.tbh_types.wl()

        # Register the builders with the context
        self.ctx.tbh_includes = self.tbh_types_includes
        self.ctx.tbh_types_decl = self.tbh_types_decl
        self.ctx.tbh_ptrs_def = self.tbh_ptrs_def
        self.ctx.tbh_types_def = self.tbh_types_def

        # Close header file
        self.tbh_types.wl()
        self.tbh_types.wb("""
        #ifdef __cplusplus
        }  // extern "C"
        #endif

        #endif  // Header guard
        """)

    def emit_types(self) -> None:
        """
        Emit all types
        """
        for fqn, w_type in self.c_types.types:
            self.emit_type(fqn, w_type)

    def emit_type(self, fqn: FQN, w_type: W_Type) -> None:
        """
        Emit a single type
        """
        assert fqn == w_type.fqn  # sanity check
        if isinstance(w_type, W_StructType):
            self.emit_StructType(fqn, w_type)
        elif isinstance(w_type, W_PtrType):
            self.emit_PtrType(fqn, w_type)
        elif isinstance(w_type, W_LiftedType):
            self.emit_LiftedType(fqn, w_type)
        else:
            assert False, f'Unknown type: {w_type}'

    def emit_StructType(self, fqn: FQN, w_st: W_StructType) -> None:
        c_st = C_Type(w_st.fqn.c_name)
        self.tbh_types_decl.wl(f'/* {w_st.fqn.human_name} */')
        self.tbh_types_decl.wl(f'typedef struct {c_st} {c_st};')

        # XXX this is VERY wrong: it assumes that the standard C layout
        # matches the layout computed by struct.calc_layout: as long as we use
        # only 32-bit types it should work, but eventually we need to do it
        # properly.
        tb = self.tbh_types_def
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
        self.tbh_types_decl.wb(f"""
        typedef struct {c_ptrtype} {{
            {c_itemtype} *p;
        #ifdef SPY_DEBUG
            size_t length;
        #endif
        }} {c_ptrtype};
        """)
        self.tbh_types_decl.wl()

        self.tbh_ptrs_def.wb(f"""
        SPY_PTR_FUNCTIONS({c_ptrtype}, {c_itemtype});
        #define {c_ptrtype}$NULL (({c_ptrtype}){{0}})
        """)
        self.tbh_ptrs_def.wl()

    def emit_LiftedType(self, fqn: FQN, w_hltype: W_LiftedType) -> None:
        c_hltype = C_Type(w_hltype.fqn.c_name)
        w_lltype = w_hltype.w_lltype
        c_lltype = self.ctx.w2c(w_lltype)
        self.tbh_types_decl.wb(f"""
        typedef struct {c_hltype} {{
            {c_lltype} ll;
        }} {c_hltype};
        """)
        self.tbh_types_decl.wl()

        self.tbh_ptrs_def.wb(f"""
        SPY_TYPELIFT_FUNCTIONS({c_hltype}, {c_lltype});
        """)
        self.tbh_ptrs_def.wl()
