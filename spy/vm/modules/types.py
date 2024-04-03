"""
SPy `types` module.
"""

from typing import TYPE_CHECKING
from spy.vm.module import W_Module
from spy.vm.b import B
from spy.vm.object import W_Type, W_Object, spytype, W_Dynamic, W_Void
from spy.vm.str import W_Str
from spy.vm.function import W_Func
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
    w_getattr: W_Object
    w_setattr: W_Object

    def __init__(self, name: str, w_origintype: W_Type) -> None:
        super().__init__(name, w_origintype.pyclass)
        self.w_origintype = w_origintype
        self.w_getattr = B.w_NotImplemented
        self.w_setattr = B.w_NotImplemented

    def __repr__(self) -> str:
        r = f"<spy type '{self.name}' (typedef of '{self.w_origintype.name}')>"
        return r

    @staticmethod
    def op_GETATTR(vm: 'SPyVM', w_type: W_Type, w_attr: W_Str) -> W_Dynamic:
        attr = vm.unwrap_str(w_attr)
        if attr == '__getattr__':
            return TYPES.w_typedef_get_getattr
        elif attr == '__setattr__':
            return TYPES.w_typedef_get_setattr
        else:
            return B.w_NotImplemented

    @staticmethod
    def op_SETATTR(vm: 'SPyVM', w_type: W_Type, w_attr: W_Str,
                   w_vtype: W_Type) -> W_Dynamic:
        attr = vm.unwrap_str(w_attr)
        if attr == '__getattr__':
            return TYPES.w_typedef_set_getattr
        elif attr == '__setattr__':
            return TYPES.w_typedef_set_setattr
        else:
            return B.w_NotImplemented


@TYPES.builtin
def typedef_set_getattr(vm: 'SPyVM', w_self: W_TypeDef, w_attr: W_Str,
                        w_val: W_Dynamic) -> W_Void:
    w_self.w_getattr = w_val
    return B.w_None

@TYPES.builtin
def typedef_set_setattr(vm: 'SPyVM', w_self: W_TypeDef, w_attr: W_Str,
                        w_val: W_Dynamic) -> W_Void:
    w_self.w_setattr = w_val
    return B.w_None

@TYPES.builtin
def typedef_get_getattr(vm: 'SPyVM', w_self: W_TypeDef,
                        w_attr: W_Str) -> W_Dynamic:
    return w_self.w_getattr

@TYPES.builtin
def typedef_get_setattr(vm: 'SPyVM', w_self: W_TypeDef,
                        w_attr: W_Str) -> W_Dynamic:
    return w_self.w_setattr


TYPES.add('TypeDef', W_TypeDef._w)

@TYPES.builtin
def makeTypeDef(vm: 'SPyVM', w_name: W_Str, w_origintype: W_Type) -> W_TypeDef:
    name = vm.unwrap_str(w_name)
    return W_TypeDef(name, w_origintype)
