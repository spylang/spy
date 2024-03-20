"""
SPy `types` module.
"""

from dataclasses import dataclass
from spy.vm.module import W_Module
from spy.vm.object import W_Type, W_Object
from spy.vm.str import W_Str
from spy.vm.registry import ModuleRegistry

TYPES = ModuleRegistry('types', '<types>')
TYPES.add('module', W_Module._w)

@dataclass
class W_Typedef(W_Type):
    """
    A Typedef is a purely static alias for another type (called "origin
    type").

    Objects can be converted from and to the Typedef, but the object itself
    will remain unchanged (and it's dynamic type will stay the same).

    The point of a Typedef is to be able to override special methods such as
    __getattr__ and __setattr__
    """
    w_origintype: W_Type

    def __init__(self, name: str, w_origintype: W_Type) -> None:
        super().__init__(name, w_origintype.pyclass)
        self.w_origintype = w_origintype

    def __repr__(self) -> str:
        r = f"<spy type '{self.name}' (typedef of '{self.w_origintype.name}')>"
        return r


@TYPES.primitive('def(name: str, t: type) -> type')
def Typedef(vm: 'SPyVM', w_name: W_Str, w_origintype: W_Type) -> W_Type:
    name = vm.unwrap_str(w_name)
    return W_Typedef(name, w_origintype)
