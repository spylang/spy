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
from spy.vm.builtin import builtin_func, builtin_method
from spy.vm.registry import ModuleRegistry
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

TYPES = ModuleRegistry('types')
TYPES.add('module', W_Module._w)


FIELDS_T = dict[str, W_Type]
METHODS_T = dict[str, W_Func]

@TYPES.builtin_type('LiftedType')
class W_LiftedType(W_Type):
    w_lltype: W_Type  # low level type

    @classmethod
    def declare(cls, fqn: FQN) -> 'Self':
        return super().declare(fqn, W_LiftedObject)

    def setup(self, fields: FIELDS_T, methods: METHODS_T) -> None:
        super().setup()
        assert set(fields.keys()) == {'__ll__'} # XXX raise proper exception
        self.w_lltype = fields['__ll__']
        for key, w_meth in methods.items():
            assert isinstance(w_meth, W_Func)
            self.dict_w[key] = w_meth

    def __repr__(self) -> str:
        lltype = self.w_lltype.fqn.human_name
        return f"<spy type '{self.fqn}' (lifted from '{lltype}')>"

    @builtin_method('__CALL_METHOD__', color='blue')
    @staticmethod
    def w_CALL_METHOD(vm: 'SPyVM', wop_self: W_OpArg, wop_method: W_OpArg,
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
            assert isinstance(w_hltype, W_LiftedType)
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

    @builtin_method('__GET___ll____', color='blue')
    @staticmethod
    def w_GET___ll__(vm: 'SPyVM', wop_hl: W_OpArg,
                      wop_attr: W_OpArg) -> W_OpImpl:
        w_hltype = wop_hl.w_static_type
        HL = Annotated[W_LiftedObject, w_hltype]
        LL = Annotated[W_Object, w_hltype.w_lltype]

        @builtin_func(w_hltype.fqn, '__unlift__')
        def w_unlift(vm: 'SPyVM', w_hl: HL) -> LL:
            return w_hl.w_ll
        return W_OpImpl(w_unlift, [wop_hl])
