"""
SPy `types` module.
"""

from typing import TYPE_CHECKING, Annotated
from spy.vm.primitive import W_Void
from spy.vm.module import W_Module
from spy.vm.b import B
from spy.vm.object import W_Type, W_Object, spytype, W_Dynamic, Member
from spy.vm.str import W_Str
from spy.vm.function import W_Func
from spy.vm.opimpl import W_OpImpl
from spy.vm.registry import ModuleRegistry
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


TYPES = ModuleRegistry('types')
TYPES.add('module', W_Module._w)


@TYPES.spytype('TypeDef')
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

    def __init__(self, name: str, w_origintype: W_Type) -> None:
        super().__init__(name, w_origintype.pyclass)
        self.w_origintype = w_origintype
        self.w_getattr = W_OpImpl.NULL
        self.w_setattr = W_OpImpl.NULL

    @staticmethod
    def w_spy_new(vm: 'SPyVM', w_cls: W_Type, w_name: W_Str,
                  w_origintype: W_Type) -> 'W_TypeDef':
        name = vm.unwrap_str(w_name)
        return W_TypeDef(name, w_origintype)

    def __repr__(self) -> str:
        r = f"<spy type '{self.name}' (typedef of '{self.w_origintype.name}')>"
        return r
