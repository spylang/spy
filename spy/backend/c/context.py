from dataclasses import dataclass
from spy.vm.vm import SPyVM, Builtins as B
from spy.vm.object import W_Type
from spy.vm.function import W_FunctionType

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
    _d: dict[W_Type, C_Type]

    def __init__(self, vm: SPyVM) -> None:
        self.vm = vm
        self._d = {}
        self._d[B.w_void] = C_Type('void')
        self._d[B.w_i32] = C_Type('int32_t')
        self._d[B.w_bool] = C_Type('bool')
        self._d[B.w_str] = C_Type('spy_Str *')

    def w2c(self, w_type: W_Type) -> C_Type:
        if w_type in self._d:
            return self._d[w_type]
        raise NotImplementedError(f'Cannot translate type {w_type} to C')

    def c_function(self, name: str, w_functype: W_FunctionType) -> C_Function:
        c_restype = self.w2c(w_functype.w_restype)
        c_params = [
            C_FuncParam(name=p.name, c_type=self.w2c(p.w_type))
            for p in w_functype.params
        ]
        return C_Function(name, c_params, c_restype)
