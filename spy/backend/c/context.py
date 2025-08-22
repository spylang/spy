from dataclasses import dataclass
from spy.fqn import FQN
from spy.vm.vm import SPyVM
from spy.vm.b import B
from spy.vm.object import W_Type
from spy.vm.function import W_Func, W_ASTFunc
from spy.vm.modules.types import W_LiftedType
from spy.vm.modules.rawbuffer import RB
from spy.vm.modules.jsffi import JSFFI
from spy.vm.modules.unsafe.ptr import W_PtrType
from spy.vm.modules.unsafe.struct import W_StructType
from spy.textbuilder import TextBuilder

@dataclass
class C_Type:
    """
    Just a tiny wrapper around a string, but it helps to make things tidy.
    """
    name: str

    def __repr__(self) -> str:
        return f"<C type '{self.name}'>"

    def __str__(self) -> str:
        return self.name

@dataclass
class C_FuncParam:
    name: str
    c_type: C_Type


@dataclass
class C_Function:
    name: str
    params: list[C_FuncParam]
    c_restype: C_Type

    def __repr__(self) -> str:
        return f"<C func '{self.name}'>"

    def decl(self) -> str:
        if self.params == []:
            s_params = 'void'
        else:
            paramlist = [f'{p.c_type} {p.name}' for p in self.params]
            s_params = ', '.join(paramlist)
        #
        return f'{self.c_restype} {self.name}({s_params})'


class Context:
    """
    Global context of the C writer.

    Keep track of things like the mapping from W_* types to C types.
    """
    vm: SPyVM
    tbh_includes: TextBuilder
    tbh_types_decl: TextBuilder
    tbh_ptrs_def: TextBuilder
    tbh_types_def: TextBuilder
    seen_modules: set[str]
    _d: dict[W_Type, C_Type]

    def __init__(self, vm: SPyVM) -> None:
        self.vm = vm
        self.seen_modules = set()
        # set by CModuleWriter.emit_header
        self.tbh_includes = None   # type: ignore
        self.tbh_types_decl = None # type: ignore
        self.tbh_ptrs_def = None   # type: ignore
        self.tbh_types_def = None  # type: ignore
        self._d = {}
        self._d[B.w_NoneType] = C_Type('void')
        self._d[B.w_i8] = C_Type('int8_t')
        self._d[B.w_u8] = C_Type('uint8_t')
        self._d[B.w_i32] = C_Type('int32_t')
        self._d[B.w_f64] = C_Type('double')
        self._d[B.w_bool] = C_Type('bool')
        self._d[B.w_str] = C_Type('spy_Str *')
        self._d[RB.w_RawBuffer] = C_Type('spy_RawBuffer *')
        self._d[JSFFI.w_JsRef] = C_Type('JsRef')

    def w2c(self, w_T: W_Type) -> C_Type:
        if w_T in self._d:
            return self._d[w_T]
        elif isinstance(w_T, W_PtrType):
            return self.new_ptr_type(w_T)
        elif isinstance(w_T, W_StructType):
            return self.new_struct_type(w_T)
        elif isinstance(w_T, W_LiftedType):
            return self.new_lifted_type(w_T)
        raise NotImplementedError(f'Cannot translate type {w_T} to C')

    def c_restype_by_fqn(self, fqn: FQN) -> C_Type:
        w_func = self.vm.lookup_global(fqn)
        assert isinstance(w_func, W_Func)
        w_restype = w_func.w_functype.w_restype
        return self.w2c(w_restype)

    def c_function(self, name: str, w_func: W_ASTFunc) -> C_Function:
        w_functype = w_func.w_functype
        argnames = [arg.name for arg in w_func.funcdef.args]
        c_restype = self.w2c(w_functype.w_restype)
        c_params = [
            C_FuncParam(name=name, c_type=self.w2c(p.w_type))
            for name, p in zip(argnames, w_functype.params, strict=True)
        ]
        return C_Function(name, c_params, c_restype)

    def new_ptr_type(self, w_ptrtype: W_PtrType) -> C_Type:
        self.add_include_maybe(w_ptrtype.w_itemtype.fqn)
        c_ptrtype = C_Type(w_ptrtype.fqn.c_name)
        self._d[w_ptrtype] = c_ptrtype
        return c_ptrtype

    def new_struct_type(self, w_st: W_StructType) -> C_Type:
        self.add_include_maybe(w_st.fqn)
        c_struct_type = C_Type(w_st.fqn.c_name)
        self._d[w_st] = c_struct_type
        return c_struct_type

    def new_lifted_type(self, w_hltype: W_LiftedType) -> C_Type:
        self.add_include_maybe(w_hltype.fqn)
        c_hltype = C_Type(w_hltype.fqn.c_name)
        self._d[w_hltype] = c_hltype
        return c_hltype

    def add_include_maybe(self, fqn: FQN) -> None:
        modname = fqn.modname
        if modname in self.seen_modules:
            # we already encountered this module, nothing to do
            return

        self.seen_modules.add(modname)
        w_mod = self.vm.modules_w[modname]
        if not w_mod.is_builtin():
            self.tbh_includes.wl(f'#include "{modname}.h"')
