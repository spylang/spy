"""
SPy `types` module.
"""

from typing import TYPE_CHECKING, Annotated, Any
from dataclasses import dataclass
from spy.fqn import FQN
from spy.vm.builtin import builtin_type
from spy.vm.primitive import W_Dynamic, W_Void
from spy.vm.module import W_Module
from spy.vm.b import B
from spy.vm.object import W_Type, W_Object, Member
from spy.vm.str import W_Str
from spy.vm.function import W_Func
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.builtin import builtin_func
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

@TYPES.builtin_type('LiftedType')
class W_LiftedType(W_Type):
    w_lltype: W_Type  # low level type

    def __init__(self, fqn: FQN, fields: FIELDS_T) -> None:
        super().__init__(fqn, W_LiftedObject)
        assert set(fields.keys()) == {'__ll__'} # XXX raise proper exception
        self.w_lltype = fields['__ll__']

    def __repr__(self) -> str:
        lltype = self.w_lltype.fqn.human_name
        return f"<spy type '{self.fqn}' (lifted from '{lltype}')>"

    @staticmethod
    def op_CALL_METHOD(vm: 'SPyVM', wop_self: W_OpArg, wop_method: W_OpArg,
                       *args_wop: W_OpArg) -> W_OpImpl:
        meth = wop_method.blue_unwrap_str(vm)
        if meth != '__lift__':
            return W_OpImpl.NULL

        w_hltype = wop_self.w_blueval
        assert isinstance(w_hltype, W_LiftedType)
        HL = Annotated[W_LiftedObject, w_hltype]
        LL = Annotated[W_Object, w_hltype.w_lltype]

        @builtin_func(w_hltype.fqn, '__lift__')
        def w_lift(vm: 'SPyVM', w_ll: LL) -> HL:
            return W_LiftedObject(w_hltype, w_ll)

        return W_OpImpl(w_lift, list(args_wop))


@dataclass
class UnwrappedLiftedObject:
    """
    Return value of vm.unwrap(w_some_lifted_object).
    Mostly useful for tests.
    """
    w_hltype: W_LiftedType
    llval: Any


class W_LiftedObject(W_Object):
    w_hltype: W_LiftedType  # high level type
    w_ll: W_Object

    def __init__(self, w_hltype: W_LiftedType, w_ll: W_Object) -> None:
        assert isinstance(w_ll, w_hltype.w_lltype.pyclass)
        self.w_hltype = w_hltype
        self.w_ll = w_ll

    def spy_get_w_type(self, vm: 'SPyVM') -> W_Type:
        return self.w_hltype

    def spy_unwrap(self, vm: 'SPyVM') -> UnwrappedLiftedObject:
        return UnwrappedLiftedObject(
            self.w_hltype,
            vm.unwrap(self.w_ll),
        )

    def __repr__(self) -> str:
        ll_repr = repr(self.w_ll)
        hltype = self.w_hltype.fqn.human_name
        return f'<{hltype} (lifted from {ll_repr})>'

    @staticmethod
    def op_GET___ll__(vm: 'SPyVM', wop_hl: W_OpArg,
                      wop_attr: W_OpArg) -> W_OpArg:
        w_hltype = wop_hl.w_static_type
        HL = Annotated[W_LiftedObject, w_hltype]
        LL = Annotated[W_Object, w_hltype.w_lltype]

        @builtin_func(w_hltype.fqn, '__unlift__')
        def w_unlift(vm: 'SPyVM', w_hl: HL) -> LL:
            return w_hl.w_ll
        return W_OpImpl(w_unlift, [wop_hl])
