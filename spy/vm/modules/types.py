"""
SPy `types` module.
"""

from typing import TYPE_CHECKING, Annotated
from spy.fqn import FQN
from spy.vm.builtin import builtin_type
from spy.vm.primitive import W_Dynamic, W_Void
from spy.vm.module import W_Module
from spy.vm.b import B
from spy.vm.object import W_Type, W_Object, Member
from spy.vm.str import W_Str
from spy.vm.function import W_Func
from spy.vm.opimpl import W_OpImpl
from spy.vm.registry import ModuleRegistry
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


TYPES = ModuleRegistry('types')
TYPES.add('module', W_Module._w)


@TYPES.builtin_type('TypeDef')
class W_TypeDef(W_Type):
    """
    A TypeDef is a purely static alias for another type (called "origin
    type").

    Objects can be converted from and to the TypeDef, but the object itself
    will remain unchanged (and it's dynamic type will stay the same).

    The point of a TypeDef is to be able to override special methods such as
    __getattr__ and __setattr__
    """
    w_origintype: W_Type
    w_getattr: Annotated[W_Dynamic, Member('__getattr__')]
    w_setattr: Annotated[W_Dynamic, Member('__setattr__')]

    def __init__(self, fqn: FQN, w_origintype: W_Type) -> None:
        super().__init__(fqn, w_origintype.pyclass)
        self.w_origintype = w_origintype
        self.w_getattr = W_OpImpl.NULL
        self.w_setattr = W_OpImpl.NULL

    @staticmethod
    def w_spy_new(vm: 'SPyVM', w_cls: W_Type, w_name: W_Str,
                  w_origintype: W_Type) -> 'W_TypeDef':
        name = vm.unwrap_str(w_name)
        fqn = FQN(f'types::typedef::{name}')
        return W_TypeDef(fqn, w_origintype)

    def __repr__(self) -> str:
        r = f"<spy type '{self.fqn}' (typedef of '{self.w_origintype.fqn}')>"
        return r
