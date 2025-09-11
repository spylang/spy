"""
SPy `types` module.

Note that TYPES is defined in spy.vm.b, and that there are other builtin types
which are attached to it here and there (e.g. W_Module and W_Cell).
"""

from typing import TYPE_CHECKING, Annotated, Any
from dataclasses import dataclass
from spy.location import Loc
from spy.vm.b import TYPES
from spy.vm.module import W_Module
from spy.vm.object import W_Type, W_Object, ClassBody
from spy.vm.function import W_Func
from spy.vm.opspec import W_OpSpec, W_MetaArg
from spy.vm.builtin import (
    builtin_method,
    builtin_classmethod,
    builtin_property
)
from spy.vm.registry import ModuleRegistry
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@TYPES.builtin_type('Loc')
class W_Loc(W_Object):
    """
    Wrapped version of Loc.
    """
    __spy_storage_category__ = 'value'

    def __init__(self, loc: Loc) -> None:
        self.loc = loc

    def spy_key(self, vm: 'SPyVM') -> Any:
        return ('Loc', self.loc)


@TYPES.builtin_type('LiftedType')
class W_LiftedType(W_Type):
    w_lltype: W_Type  # low level type

    def define_from_classbody(self, body: ClassBody) -> None:
        super().define(W_LiftedObject)
        assert set(body.fields_w.keys()) == {'__ll__'} # XXX raise proper exc
        self.w_lltype = body.fields_w['__ll__'].w_T
        for key, w_obj in body.dict_w.items():
            assert key not in self.dict_w, 'need to think what to do'
            self.dict_w[key] = w_obj

    def repr_hints(self) -> list[str]:
        lltype = self.w_lltype.fqn.human_name
        h = f"lifted from '{lltype}'"
        return [h]


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

    @builtin_classmethod('__lift__', color='blue', kind='metafunc')
    @staticmethod
    def w_LIFT(vm: 'SPyVM', wam_T: W_MetaArg, wam_from: W_MetaArg) -> W_OpSpec:
        w_hltype = wam_T.w_blueval
        assert isinstance(w_hltype, W_LiftedType)
        HL = Annotated[W_LiftedObject, w_hltype]
        LL = Annotated[W_Object, w_hltype.w_lltype]

        @vm.register_builtin_func(w_hltype.fqn, '__lift__')
        def w_lift(vm: 'SPyVM', w_ll: LL) -> HL:
            assert isinstance(w_hltype, W_LiftedType)
            return W_LiftedObject(w_hltype, w_ll)
        return W_OpSpec(w_lift, [wam_from])


    @builtin_property('__ll__', color='blue', kind='metafunc')
    @staticmethod
    def w_GET_ll(vm: 'SPyVM', wam_hl: W_MetaArg) -> W_OpSpec:
        w_hltype = wam_hl.w_static_T
        HL = Annotated[W_LiftedObject, w_hltype]
        LL = Annotated[W_Object, w_hltype.w_lltype]

        @vm.register_builtin_func(w_hltype.fqn, '__unlift__')
        def w_unlift(vm: 'SPyVM', w_hl: HL) -> LL:
            return w_hl.w_ll
        return W_OpSpec(w_unlift, [wam_hl])
