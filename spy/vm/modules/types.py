"""
SPy `types` module.
"""

from typing import TYPE_CHECKING, Annotated
from spy.vm.module import W_Module
from spy.vm.b import B
from spy.vm.object import W_Type, W_Object, spytype, W_Dynamic, W_Void, Member
from spy.vm.str import W_Str
from spy.vm.function import W_Func
from spy.vm.list import W_BaseList
from spy.vm.registry import ModuleRegistry
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


TYPES = ModuleRegistry('types', '<types>')
TYPES.add('module', W_Module._w)


@spytype('TypeDef')
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

    def __init__(self, vm: 'SPyVM', name: str, w_origintype: W_Type,
                 w_descriptors: W_Dynamic) -> None:
        super().__init__(name, w_origintype.pyclass)
        self.w_origintype = w_origintype
        self.w_getattr = B.w_NotImplemented
        self.w_setattr = B.w_NotImplemented
        self.w_descriptors = w_descriptors
        self.__spy_descriptors__ = {}
        #
        assert isinstance(w_descriptors, W_BaseList)
        for w_descr in w_descriptors.items_w:
            name = vm.unwrap_str(w_descr.w_name)
            self.__spy_descriptors__[name] = w_descr


    def __repr__(self) -> str:
        r = f"<spy type '{self.name}' (typedef of '{self.w_origintype.name}')>"
        return r

TYPES.add('TypeDef', W_TypeDef._w)

@TYPES.builtin
def makeTypeDef(vm: 'SPyVM', w_name: W_Str, w_origintype: W_Type,
                w_descriptors: W_Dynamic) -> W_TypeDef:
    name = vm.unwrap_str(w_name)
    return W_TypeDef(vm, name, w_origintype, w_descriptors)
