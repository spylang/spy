from dataclasses import dataclass
import typing
from spy.vm.object import W_Object, W_Type
from spy.vm.module import W_Module
from spy.vm.codeobject import W_CodeObject
from spy.vm.varstorage import VarStorage
if typing.TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@dataclass
class FuncParam:
    name: str
    w_type: W_Type

def make_params(**kwargs: W_Type) -> list[FuncParam]:
    """
    Small helper to make it easier to build a list of FuncParam, especially in
    tests
    """
    return [FuncParam(key, w_type) for key, w_type in kwargs.items()]

@dataclass(repr=False)
class W_FunctionType(W_Type):
    params: list[FuncParam]
    w_restype: W_Type

    def __init__(self, params: list[FuncParam], w_restype: W_Type):
        # sanity check
        if params:
            assert isinstance(params[0], FuncParam)
        self.params = params
        self.w_restype = w_restype
        sig = self._str_sig()
        super().__init__(f'fn {sig}', W_Function)

    def _str_sig(self) -> str:
        params = [f'{p.name}: {p.w_type.name}' for p in self.params]
        str_params = ', '.join(params)
        resname = self.w_restype.name
        return f'({str_params}) -> {resname}'


class W_Function(W_Object):
    w_functype: W_FunctionType
    w_code: W_CodeObject
    globals: VarStorage

    def __init__(self, w_functype: W_FunctionType, w_code: W_CodeObject,
                 globals: VarStorage) -> None:
        self.w_functype = w_functype
        self.w_code = w_code
        self.globals = globals

    def __repr__(self) -> str:
        return f"<spy function '{self.w_code.name}'>"

    def spy_get_w_type(self, vm: 'SPyVM') -> W_Type:
        return self.w_functype
