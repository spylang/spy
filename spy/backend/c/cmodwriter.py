from typing import Optional, Iterable
import itertools
import py.path
from spy.fqn import FQN
from spy.vm.object import W_Type, W_Object
from spy.vm.module import W_Module, ModItem
from spy.vm.primitive import W_I32
from spy.vm.function import W_ASTFunc, W_BuiltinFunc
from spy.vm.vm import SPyVM
from spy.vm.modules.types import W_LiftedType
from spy.vm.modules.unsafe.ptr import W_PtrType, W_Ptr
from spy.vm.modules.unsafe.struct import W_StructType
from spy.textbuilder import TextBuilder
from spy.backend.c.context import Context, C_Type
from spy.backend.c.cwriter import CFuncWriter
from spy.backend.c.cffiwriter import CFFIWriter


class CModuleWriter:
    ctx: Context
    w_mod: W_Module
    spyfile: Optional[py.path.local]
    hfile: Optional[py.path.local]
    cfile: Optional[py.path.local]
    global_vars: set[str]
    mod_items: Iterable[ModItem]
    jsffi_error_emitted: bool = False

    # main and nested TextBuilders for .h
    tbh: TextBuilder
    tbh_warnings: TextBuilder
    tbh_types_decl: TextBuilder  # forward type declarations
    tbh_types_def: TextBuilder   # type definitions
    tbh_ptrs_def: TextBuilder    # ptr and typelift accessors
    tbh_funcs: TextBuilder       # function declarations
    tbh_globals: TextBuilder     # global var declarations (.h)

    # main and nested TextBuilders for .c
    tbc: TextBuilder
    tbc_funcs: TextBuilder       # functions
    tbc_globals: TextBuilder     # global var definition (.c)

    def __init__(
            self,
            vm: SPyVM,
            w_mod: W_Module,
            spyfile: Optional[py.path.local],
            hfile: Optional[py.path.local],
            cfile: Optional[py.path.local],
            cffi: CFFIWriter,
            *,
            mod_items: Optional[Iterable[ModItem]] = None,
    ) -> None:
        self.ctx = Context(vm)
        self.w_mod = w_mod
        if mod_items is None:
            self.mod_items = w_mod.items_w()
        else:
            self.mod_items = mod_items
        self.spyfile = spyfile
        self.hfile = hfile
        self.cfile = cfile
        self.cffi = cffi
        self.tbh = TextBuilder(use_colors=False)
        self.tbc = TextBuilder(use_colors=False)
        # nested builders are initialized lazily
        self.global_vars = set()
        self.init_h()
        self.init_c()

    def __repr__(self) -> str:
        return f'<CModuleWriter for {self.w_mod}>'

    def write_c_source(self) -> None:
        self.emit_content()
        if self.hfile:
            self.hfile.write(self.tbh.build())
        if self.cfile:
            self.cfile.write(self.tbc.build())

    def new_global_var(self, prefix: str) -> str:
        """
        Create an unique name for a global var whose name starts with 'prefix'
        """
        prefix = f'SPY_g_{prefix}'
        for i in itertools.count():
            varname = f'{prefix}{i}'
            if varname not in self.global_vars:
                break
        self.global_vars.add(varname)
        return varname

    def init_h(self) -> None:
        assert self.hfile is not None
        GUARD = self.hfile.purebasename.upper()
        header_guard = f"SPY_{GUARD}_H"
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

        self.tbh.wl('// includes')
        self.tbh.wl('#include "builtins_extra.h"')
        self.tbh_includes = self.tbh.make_nested_builder()
        self.tbh.wl()

        self.tbh.wl('// forward type declarations')
        self.tbh_types_decl = self.tbh.make_nested_builder()
        self.tbh.wl()

        self.tbh.wl('// type definitions')
        self.tbh_types_def = self.tbh.make_nested_builder()
        self.tbh.wl()

        self.tbh.wl('// ptr and typelift accessors')
        self.tbh_ptrs_def = self.tbh.make_nested_builder()
        self.tbh.wl()

        self.tbh.wl('// function declarations')
        self.tbh_funcs = self.tbh.make_nested_builder()
        self.tbh.wl()

        self.tbh.wl('// global variable declarations')
        self.tbh_globals = self.tbh.make_nested_builder()
        self.tbh.wl()

        # Register the builders with the context
        self.ctx.tbh_includes = self.tbh_includes
        self.ctx.tbh_types_decl = self.tbh_types_decl
        self.ctx.tbh_ptrs_def = self.tbh_ptrs_def
        self.ctx.tbh_types_def = self.tbh_types_def

        # Close header file
        self.tbh.wl()
        self.tbh.wb("""
        #ifdef __cplusplus
        }  // extern "C"
        #endif

        #endif  // Header guard
        """)

    def init_c(self) -> None:
        assert self.hfile is not None
        header_name = self.hfile.basename
        self.cffi.emit_include(header_name)
        self.tbc.wb(f"""
        #include "{header_name}"
        """)
        if self.spyfile is not None:
            self.tbc.wb(f"""
            #ifdef SPY_DEBUG_C
            #    define SPY_LINE(SPY, C) C "{self.cfile}"
            #else
            #    define SPY_LINE(SPY, C) SPY "{self.spyfile}"
            #endif
            """)
        self.tbc.wl()
        self.tbc.wl('// constants and globals')
        self.tbc_globals = self.tbc.make_nested_builder()
        self.tbc.wl()
        self.tbc.wl('// content of the module')
        self.tbc.wl()
        self.tbc_content = self.tbc.make_nested_builder()

        # Main function
        fqn_main = FQN([self.w_mod.name, 'main'])
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
        for fqn, w_obj in self.mod_items:
            assert w_obj is not None, 'uninitialized global?'
            self.emit_obj(fqn, w_obj)

    def emit_obj(self, fqn: FQN, w_obj: W_Object) -> None:
        w_T = self.ctx.vm.dynamic_type(w_obj)

        if hasattr(w_obj, 'fqn') and w_obj.fqn != fqn:
            # just a reference to a function/type defined elsewhere, we can
            # ignore it
            return

        # ==== functions ====
        elif isinstance(w_obj, W_ASTFunc):
            # emit red functions, ignore blue ones
            if w_obj.color == 'red':
                self.emit_func(fqn, w_obj)

        elif isinstance(w_obj, W_BuiltinFunc):
            # ignore builtin functions
            pass

        # ==== types ====
        elif isinstance(w_obj, W_StructType):
            self.emit_StructType(fqn, w_obj)

        elif isinstance(w_obj, W_PtrType):
            self.emit_PtrType(fqn, w_obj)

        elif isinstance(w_obj, W_LiftedType):
            self.emit_LiftedType(fqn, w_obj)

        # ==== vars/consts ====
        elif isinstance(w_obj, W_I32):
            intval = self.ctx.vm.unwrap(w_obj)
            c_type = self.ctx.w2c(w_T)
            self.tbh_globals.wl(f'extern {c_type} {fqn.c_name};')
            self.tbc_globals.wl(f'{c_type} {fqn.c_name} = {intval};')

        elif isinstance(w_T, W_PtrType):
            # for now, we only support NULL constnts
            assert isinstance(w_obj, W_Ptr)
            assert w_obj.addr == 0, 'only NULL pointers can be stored in constants for now'
            c_type = self.ctx.w2c(w_T)
            self.tbh_globals.wl(f'extern {c_type} {fqn.c_name};')
            self.tbc_globals.wl(f'{c_type} {fqn.c_name} = {{0}};')

        elif isinstance(w_T, W_Type) and w_T.fqn.modname == 'builtins':
            # this is an ad-hoc hack to support things like this at
            # module-level:
            #    T = i32
            pass

        else:
            # struct types are already handled in the header
            raise NotImplementedError('WIP')

    def emit_func(self, fqn: FQN, w_func: W_ASTFunc) -> None:
        # func prototype in .h
        c_func = self.ctx.c_function(fqn.c_name, w_func)
        self.tbh_funcs.wl(c_func.decl() + ';')

        # func body in .c
        fw = CFuncWriter(self.ctx, self, fqn, w_func)
        fw.emit()

        # cffi wrapper
        self.cffi.emit_func(self.ctx, fqn, w_func)

    def emit_StructType(self, fqn: FQN, w_st: W_StructType) -> None:
        c_st = C_Type(w_st.fqn.c_name)
        self.tbh_types_decl.wl(f'typedef struct {c_st} {c_st};')

        # XXX this is VERY wrong: it assumes that the standard C layout
        # matches the layout computed by struct.calc_layout: as long as we use
        # only 32-bit types it should work, but eventually we need to do it
        # properly.
        tb = self.tbh_types_def
        tb.wl("struct %s {" % c_st)
        with tb.indent():
            for field, w_fieldtype in w_st.fields.items():
                c_fieldtype = self.ctx.w2c(w_fieldtype)
                tb.wl(f"{c_fieldtype} {field};")
        tb.wl("};")
        tb.wl("")

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
