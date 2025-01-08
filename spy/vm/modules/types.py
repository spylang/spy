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


@TYPES.builtin_type('ForwardRef')
class W_ForwardRef(W_Type):
    """
    A ForwardRef represent a type which has been declared but not defined
    yet.
    It can `become()` an actual type while preserving identity, so that
    existing references to the forward ref are automatically updated.

    It is primarily used to predeclare types in a module, so they can be
    referenced in advance before their actual definition. Consider the
    following example:

        def foo(p: Point) -> void:
            pass

        class Point:
            pass

    When executing the module, there are implicit statements, shown below:

        Point = ForwardRef('test::Point')

        def foo(p: Point) -> void:
            pass

        # here foo's signature is 'def(x: ForwardRef(`test::Point`))'

        class Point:
            ...
        `test::Point`.become(Point)
        # now, foo's signature is 'def(x: Point)'.
    """
    fqn: FQN

    def __init__(self, fqn: FQN) -> None:
        super().__init__(fqn, pyclass=W_Object)

    def __repr__(self) -> str:
        return f"<ForwardRef '{self.fqn}'>"

    def become(self, w_T: W_Type) -> None:
        assert self.fqn == w_T.fqn
        self.__class__ = w_T.__class__  # type: ignore
        self.__dict__ = w_T.__dict__



FIELDS_T = dict[str, W_Type]

class W_TypedefType(W_Type):
    w_innertype: W_Type

    def __init__(self, fqn: FQN, fields: FIELDS_T) -> None:
        super().__init__(fqn, W_TypedefInst)
        assert set(fields.keys()) == {'__inner__'} # XXX raise proper exception
        self.w_innertype = fields['__inner__']

    def __repr__(self) -> str:
        inner = self.w_innertype.fqn.human_name
        return f"<spy type '{self.fqn}' (typedef of '{inner}' )>"


class W_TypedefInst(W_Object):
    pass
