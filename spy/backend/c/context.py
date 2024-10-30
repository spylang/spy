from dataclasses import dataclass
from spy.fqn import FQN
from spy.vm.vm import SPyVM
from spy.vm.b import B
from spy.vm.object import W_Type
from spy.vm.function import W_FuncType
from spy.vm.modules.rawbuffer import RB
from spy.vm.modules.types import W_TypeDef
from spy.vm.modules.jsffi import JSFFI
from spy.vm.modules.unsafe import UNSAFE
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
    out_types: TextBuilder
    _d: dict[W_Type, C_Type]

    def __init__(self, vm: SPyVM) -> None:
        self.vm = vm
        self.out_types = None # set by CModuleWriter.emit_module
        self._d = {}
        self._d[B.w_void] = C_Type('void')
        self._d[B.w_i32] = C_Type('int32_t')
        self._d[B.w_f64] = C_Type('double')
        self._d[B.w_bool] = C_Type('bool')
        self._d[B.w_str] = C_Type('spy_Str *')
        self._d[RB.w_RawBuffer] = C_Type('spy_RawBuffer *')
        self._d[JSFFI.w_JsRef] = C_Type('JsRef')

    def w2c(self, w_type: W_Type) -> C_Type:
        if isinstance(w_type, W_TypeDef):
            w_type = w_type.w_origintype
        if w_type in self._d:
            return self._d[w_type]
        elif self.vm.issubclass(w_type, UNSAFE.w_ptr):
            return self.new_ptr_type(w_type)
        elif isinstance(w_type, W_StructType):
            return self.new_struct_type(w_type)
        raise NotImplementedError(f'Cannot translate type {w_type} to C')

    def c_restype_by_fqn(self, fqn: FQN) -> C_Type:
        w_func = self.vm.lookup_global(fqn)
        w_restype = w_func.w_functype.w_restype
        return self.w2c(w_restype)

    def c_function(self, name: str, w_functype: W_FuncType) -> C_Function:
        c_restype = self.w2c(w_functype.w_restype)
        c_params = [
            C_FuncParam(name=p.name, c_type=self.w2c(p.w_type))
            for p in w_functype.params
        ]
        return C_Function(name, c_params, c_restype)

    def new_ptr_type(self, w_ptrtype: W_Type) -> C_Type:
        # XXX this way of computing the typename works only for simple
        # types. To handle more complex types we need to give each of them an
        # FQN, and probably we also need to think how to generate .h files
        w_itemtype = w_ptrtype.pyclass.w_itemtype  # B.w_i32
        c_itemtype = self.w2c(w_itemtype)          # int32_t
        t = w_itemtype.name                        # i32
        ptr = f'spy_unsafe$ptr_{t}'                # spy_unsafe$ptr_i32
        c_type = C_Type(ptr)
        self.out_types.wl(f"SPY_DEFINE_PTR_TYPE({c_type}, {c_itemtype})")
        self._d[w_ptrtype] = c_type
        return c_type

    def new_struct_type(self, w_st: W_StructType) -> C_Type:
        # XXX same comment about typename vs FQN as above.
        #
        # XXX this is VERY wrong: it assumes that the standard C layout
        # matches the layout computed by struct.calc_layout: as long as we use
        # only 32-bit types it should work, but eventually we need to do it
        # properly.
        t = w_st.name
        self.out_types.wl("typedef struct {")
        with self.out_types.indent():
            for field, w_fieldtype in w_st.fields.items():
                c_fieldtype = self.w2c(w_fieldtype)
                self.out_types.wl(f"{c_fieldtype} {field};")
        self.out_types.wl("} %s;" % t)
        self.out_types.wl("")
        c_type = C_Type(t)
        self._d[w_st] = c_type
        return c_type
