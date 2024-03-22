"""
SPy `types` module.
"""

from spy.vm.module import W_Module
from spy.vm.object import W_Type, W_Object, spytype
from spy.vm.str import W_Str
from spy.vm.function import W_Func
from spy.vm.registry import ModuleRegistry

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
    w_getattr: W_Func
    w_setattr = W_Func

    def __init__(self, name: str, w_origintype: W_Type) -> None:
        super().__init__(name, w_origintype.pyclass)
        self.w_origintype = w_origintype
        self.w_getattr = None
        self.w_setattr = None

    def __repr__(self) -> str:
        r = f"<spy type '{self.name}' (typedef of '{self.w_origintype.name}')>"
        return r

    def spy_getattr(self, vm: 'SPyVM', w_attr: str) -> W_Object:
        attr = vm.unwrap_str(w_attr)
        if attr == '__getattr__':
            return self.w_getattr
        elif attr == '__setattr__':
            return self.w_setattr
        raise Exception(f"invalid attribute: {attr}") # XXX better error

    def spy_setattr(self, vm: 'SPyVM', w_attr: str, w_val: W_Object) -> W_Object:
        attr = vm.unwrap_str(w_attr)
        if attr == '__getattr__':
            self.w_getattr = w_val
            return
        elif attr == '__setattr__':
            self.w_setattr = w_val
            return
        raise Exception(f"invalid attribute: {attr}") # XXX better error


TYPES.add('TypeDef', W_TypeDef._w)

@TYPES.primitive('def(name: str, t: type) -> TypeDef')
def makeTypeDef(vm: 'SPyVM', w_name: W_Str, w_origintype: W_Type) -> W_TypeDef:
    name = vm.unwrap_str(w_name)
    return W_TypeDef(name, w_origintype)
