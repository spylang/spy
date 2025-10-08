from typing import TYPE_CHECKING, Optional
from spy.fqn import FQN
from spy.vm.object import W_Type
from spy.vm.struct import W_StructType
from spy.vm.modules.types import W_LiftedType
from spy.vm.modules.unsafe.ptr import W_PtrType
from spy.textbuilder import TextBuilder
from spy.backend.c.context import Context, C_Type

if TYPE_CHECKING:
    from spy.backend.c.cmodwriter import CModule


class CTypesWriter:
    ctx: Context
    c_mod: 'CModule'

    # main and nested TextBuilders for _types.h
    tbh_types: TextBuilder
    tbh_types_includes: TextBuilder
    tbh_types_decl: TextBuilder  # forward type declarations
    tbh_types_def: TextBuilder   # type definitions
    tbh_ptrs_def: TextBuilder    # ptr and typelift accessors

    def __init__(self, ctx: Context, c_mod: 'CModule') -> None:
        self.ctx = ctx
        self.c_mod = c_mod
        self.tbh_types = TextBuilder(use_colors=False)
        self.init_h_types()

    def __repr__(self) -> str:
        return f'<CTypesWriter for {self.c_mod.modname}>'

    def write_types_header(self) -> None:
        """
        Write the _types.h file for this module
        """
        self.emit_types()
        if self.c_mod.hfile_types:
            self.c_mod.hfile_types.write(self.tbh_types.build())

    def init_h_types(self) -> None:
        assert self.c_mod.hfile_types is not None
        GUARD = self.c_mod.hfile_types.purebasename.upper()
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
        # Don't include ptrs_builtins.h for ptrs_builtins itself
        if self.c_mod.modname != 'ptrs_builtins':
            self.tbh_types.wl('#include "ptrs_builtins.h"')
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

        # Register the type-specific builders with the context
        # Note: we don't register tbh_includes because CModuleWriter
        # has its own includes builder for the main .h file
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
        Emit all types from this module
        """
        for fqn, w_type in self.c_mod.types:
            assert w_type is not None, 'uninitialized type?'
            self.emit_type(fqn, w_type)

    def emit_type(self, fqn: FQN, w_type: W_Type) -> None:
        """
        Emit a single type
        """
        if hasattr(w_type, 'fqn'):
            assert fqn == w_type.fqn  # sanity check

        if isinstance(w_type, W_StructType):
            self.emit_StructType(fqn, w_type)
        elif isinstance(w_type, W_PtrType):
            self.emit_PtrType(fqn, w_type)
        elif isinstance(w_type, W_LiftedType):
            self.emit_LiftedType(fqn, w_type)
        else:
            raise NotImplementedError(f'Unknown type: {type(w_type)}')

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
        #
        # unsafe::ptr to struct are a special case: in theory the belong to
        # the 'unsafe' module, but it makes more sense to emit them in the
        # same module as their struct
        fqn_ptr = FQN('unsafe').join('ptr', [fqn])
        w_ptrtype = self.ctx.vm.lookup_global(fqn_ptr)
        if w_ptrtype is not None:
            assert isinstance(w_ptrtype, W_PtrType)
            self.emit_PtrType(fqn_ptr, w_ptrtype)

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
