from typing import Optional, Any
from types import NoneType
import itertools
import py.path
from spy import ast
from spy.fqn import FQN
from spy.location import Loc
from spy.vm.object import W_Type, W_Object
from spy.vm.module import W_Module
from spy.vm.function import W_ASTFunc, W_BuiltinFunc, W_FuncType, W_Func
from spy.vm.vm import SPyVM
from spy.vm.b import B
from spy.vm.modules.types import TYPES, W_LiftedType
from spy.vm.modules.unsafe.ptr import W_PtrType, W_Ptr
from spy.vm.modules.unsafe.struct import W_StructType
from spy.textbuilder import TextBuilder
from spy.backend.c.context import Context, C_Type, C_Function
from spy.backend.c import c_ast as C
from spy.backend.c.cwriter import CFuncWriter
from spy.util import shortrepr, magic_dispatch

class CModuleWriter:
    ctx: Context
    w_mod: W_Module
    spyfile: py.path.local
    cfile: py.path.local
    hfile: py.path.local
    global_vars: set[str]
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

    def __init__(self, vm: SPyVM, w_mod: W_Module,
                 spyfile: py.path.local,
                 cfile: py.path.local) -> None:
        self.ctx = Context(vm)
        self.w_mod = w_mod
        self.spyfile = spyfile
        self.cfile = cfile
        self.hfile = cfile.new(ext='.h')
        self.tbc = TextBuilder(use_colors=False)
        self.tbh = TextBuilder(use_colors=False)
        # nested builders are initialized lazily
        self.global_vars = set()

    def write_c_source(self) -> None:
        self.init_h()
        self.init_c()
        self.emit_content()
        self.hfile.write(self.tbh.build())
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
        header_guard = f"SPY_{self.w_mod.name.upper()}_H"
        self.tbh.wb(f"""
        #ifndef {header_guard}
        #define {header_guard}

        #include <spy.h>

        #ifdef __cplusplus
        extern "C" {{
        #endif
        """)
        self.tbh.wl()
        self.tbh_warnings = self.tbh.make_nested_builder()
        self.tbh.wl()

        self.tbh.wl('// includes')
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
        header_name = self.hfile.basename
        self.tbc.wb(f"""
        #include "{header_name}"

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

    def emit_content(self):
        for fqn, w_obj in self.w_mod.items_w():
            assert w_obj is not None, 'uninitialized global?'

            if isinstance(w_obj, W_ASTFunc):
                if w_obj.color == 'red':
                    self.declare_func(fqn, w_obj)
                    self.emit_func(fqn, w_obj)

            elif isinstance(w_obj, W_BuiltinFunc):
                # this is a hack. We have a variable holding a builtin
                # function: we don't support function pointers yet, so this
                # MUST be a blue variable, which we don't want to declare, so
                # we just skip it.
                #
                # Ideally, we should have a more direct way of knowing which
                # of the module content are red and blue.
                pass

            else:
                self.declare_var(fqn, w_obj)
                self.emit_var(fqn, w_obj)

    def declare_func(self, fqn: FQN, w_func: W_ASTFunc) -> None:
        """
        Generate function declaration in mod.h
        """
        argnames = [arg.name for arg in w_func.funcdef.args]
        c_func = self.ctx.c_function(fqn.c_name, w_func)
        self.tbh_funcs.wl(c_func.decl() + ';')

    def emit_func(self, fqn: FQN, w_func: W_ASTFunc) -> None:
        """
        Generate function implementation in mod.c
        """
        fw = CFuncWriter(self.ctx, self, fqn, w_func)
        fw.emit()

    def declare_var(self, fqn: FQN, w_obj: W_Object) -> None:
        """
        Generate variable declaration in mod.h
        """
        w_type = self.ctx.vm.dynamic_type(w_obj)
        if w_type is B.w_i32:
            c_type = self.ctx.w2c(w_type)
            self.tbh_globals.wl(f'extern {c_type} {fqn.c_name};')
        elif isinstance(w_obj, (W_StructType, W_LiftedType)):
            # this forces ctx to emit the struct definition
            self.ctx.w2c(w_obj)
        elif isinstance(w_type, W_PtrType):
            # for now, we only support NULL constnts
            assert isinstance(w_obj, W_Ptr)
            assert w_obj.addr == 0, 'only NULL pointers can be stored in constants for now'
            c_type = self.ctx.w2c(w_type)
            self.tbh_globals.wl(f'extern {c_type} {fqn.c_name};')
        elif isinstance(w_type, W_Type) and w_type.fqn.modname == 'builtins':
            # this is an ad-hoc hack to support things like this at
            # module-level:
            #    T = i32
            pass
        else:
            raise NotImplementedError('WIP')

    def emit_var(self, fqn: FQN, w_obj: W_Object) -> None:
        """
        Generate variable definition in mod.c
        """
        w_type = self.ctx.vm.dynamic_type(w_obj)
        if w_type is B.w_i32:
            intval = self.ctx.vm.unwrap(w_obj)
            c_type = self.ctx.w2c(w_type)
            self.tbc.wl(f'{c_type} {fqn.c_name} = {intval};')
        elif isinstance(w_obj, (W_StructType, W_LiftedType)):
            pass
        elif isinstance(w_type, W_PtrType):
            # for now, we only support NULL constnts
            assert isinstance(w_obj, W_Ptr)
            assert w_obj.addr == 0, 'only NULL pointers can be stored in constants for now'
            c_type = self.ctx.w2c(w_type)
            self.tbh_globals.wl(f'{c_type} {fqn.c_name} = {{0}};')
        elif isinstance(w_type, W_Type) and w_type.fqn.modname == 'builtins':
            # this is an ad-hoc hack to support things like this at
            # module-level:
            #    T = i32
            pass
        else:
            # struct types are already handled in the header
            raise NotImplementedError('WIP')
