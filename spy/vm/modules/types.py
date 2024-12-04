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
from spy.vm.opimpl import W_OpImpl, W_OpArg
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


@TYPES.builtin_type('ForwardRef')
class W_ForwardRef(W_Object):
    """
    A ForwardRef represent a value which has been declared but not defined
    yet.
    It can `become()` a different value while preserving identity, so that
    existing references to the forward ref are automatically updated.

    It is primarily used to predeclare types and functions in a module, so
    they can be referenced in advance before their actual definition. Consider
    the following example:

        def foo(p: Point) -> void:
            pass

        class Point:
            pass

    When executing the module, there are implicit statements, shown below:

        foo = ForwardRef('test::foo')
        Point = ForwardRef('test::Point')

        def foo(p: Point) -> void:
            pass
        `test::foo`.become(foo)

        # here foo's signature is 'def(x: ForwardRef(`test::Point`))'

        class Point:
            ...
        # `test::Point`.become(Point)
        # now, foo's signature is 'def(x: Point)'.
    """
    fqn: FQN

    def __init__(self, fqn: FQN) -> None:
        self.fqn = fqn

    def __repr__(self) -> str:
        return f"<ForwardRef '{self.fqn}'>"

    def become(self, w_val: W_Object) -> None:
        self.__class__ = w_val.__class__
        self.__dict__ = w_val.__dict__
