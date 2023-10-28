from dataclasses import dataclass
import typing
from spy.fqn import FQN
from spy.vm.object import W_Object, W_Type, W_i32
from spy.vm.module import W_Module
from spy.vm.codeobject import W_CodeObject
from spy.vm.varstorage import VarStorage
if typing.TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@dataclass
class FuncParam:
    name: str
    w_type: W_Type


@dataclass(repr=False)
class W_FunctionType(W_Type):
    params: list[FuncParam]
    w_restype: W_Type

    def __init__(self, params: list[FuncParam], w_restype: W_Type) -> None:
        # sanity check
        if params:
            assert isinstance(params[0], FuncParam)
        self.params = params
        self.w_restype = w_restype
        sig = self._str_sig()
        super().__init__(f'def{sig}', W_Function)

    @classmethod
    def make(cls, *, w_restype: W_Type, **kwargs: W_Type) -> 'W_FunctionType':
        """
        Small helper to make it easier to build W_FunctionType, especially in
        tests
        """
        params = [FuncParam(key, w_type) for key, w_type in kwargs.items()]
        return cls(params, w_restype)

    def _str_sig(self) -> str:
        params = [f'{p.name}: {p.w_type.name}' for p in self.params]
        str_params = ', '.join(params)
        resname = self.w_restype.name
        return f'({str_params}) -> {resname}'


class W_Function(W_Object):

    @property
    def w_functype(self) -> W_FunctionType:
        raise NotImplementedError

    def spy_get_w_type(self, vm: 'SPyVM') -> W_Type:
        return self.w_functype

    def spy_call(self, vm: 'SPyVM', args_w: list[W_Object]) -> W_Object:
        raise NotImplementedError


class W_UserFunction(W_Function):
    w_code: W_CodeObject

    def __init__(self, w_code: W_CodeObject) -> None:
        self.w_code = w_code

    def __repr__(self) -> str:
        return f"<spy function '{self.w_code.fqn}'>"

    @property
    def w_functype(self) -> W_FunctionType:
        return self.w_code.w_functype


class W_BuiltinFunction(W_Function):
    fqn: FQN
    _w_functype: W_FunctionType

    def __init__(self, fqn: FQN, w_functype: W_FunctionType) -> None:
        self.fqn = fqn
        self._w_functype = w_functype

    def __repr__(self) -> str:
        return f"<spy function '{self.fqn}' (builtin)>"

    @property
    def w_functype(self) -> W_FunctionType:
        return self._w_functype

    def spy_call(self, vm: 'SPyVM', args_w: list[W_Object]) -> W_Object:
        # XXX we need a way to automatically generate unwrapping code for
        # args_w. For now, let's just hardcode
        if self.fqn.fullname == 'builtins::abs':
            assert len(args_w) == 1
            arg = vm.unwrap_i32(args_w[0])
            res = vm.ll.call(self.fqn.c_name, arg)
            return vm.wrap(res)
        else:
            assert False
