from typing import TYPE_CHECKING, Literal, Annotated
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type
from spy.vm.str import W_Str
from spy.vm.builtin import builtin_func
from spy.vm.opspec import W_OpSpec, W_OpArg
from spy.vm.opimpl import W_OpImpl

from . import OP, op_fast_call
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

OpKind = Literal['get', 'set']

def unwrap_attr_maybe(vm: 'SPyVM', wop_attr: W_OpArg) -> str:
    if wop_attr.is_blue() and wop_attr.w_static_type is B.w_str:
        return vm.unwrap_str(wop_attr.w_blueval)
    else:
        return '<unknown>'

@OP.builtin_func(color='blue')
def w_GETATTR(vm: 'SPyVM', wop_obj: W_OpArg, wop_attr: W_OpArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    attr = unwrap_attr_maybe(vm, wop_attr)
    w_opspec = _get_GETATTR_opspec(vm, wop_obj, wop_attr, attr)
    return typecheck_opspec(
        vm,
        w_opspec,
        [wop_obj, wop_attr],
        dispatch = 'single',
        errmsg = "type `{0}` has no attribute '%s'" % attr
    )

def _get_GETATTR_opspec(vm: 'SPyVM', wop_obj: W_OpArg, wop_attr: W_OpArg,
                        attr: str) -> W_OpSpec:
    w_type = wop_obj.w_static_type
    if w_type is B.w_dynamic:
        return W_OpSpec(OP.w_dynamic_getattr)
    elif attr in w_type.spy_members:
        return opspec_member('get', vm, w_type, attr)
    elif w_GET := w_type.lookup_blue_func(f'__GET_{attr}__'):
        return op_fast_call(vm, w_GET, [wop_obj, wop_attr])
    elif w_GETATTR := w_type.lookup_blue_func(f'__GETATTR__'):
        return op_fast_call(vm, w_GETATTR, [wop_obj, wop_attr])
    elif w_getattr := w_type.lookup_func(f'__getattr__'):
        return W_OpSpec(w_getattr, [wop_obj, wop_attr])
    return W_OpSpec.NULL


@OP.builtin_func(color='blue')
def w_SETATTR(vm: 'SPyVM', wop_obj: W_OpArg, wop_attr: W_OpArg,
            wop_v: W_OpArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    attr = unwrap_attr_maybe(vm, wop_attr)
    w_opspec = _get_SETATTR_opspec(vm, wop_obj, wop_attr, wop_v, attr)
    errmsg = "type `{0}` does not support assignment to attribute '%s'" % attr
    return typecheck_opspec(
        vm,
        w_opspec,
        [wop_obj, wop_attr, wop_v],
        dispatch = 'single',
        errmsg = errmsg
    )

def _get_SETATTR_opspec(vm: 'SPyVM', wop_obj: W_OpArg, wop_attr: W_OpArg,
                        wop_v: W_OpArg, attr: str) -> W_OpSpec:
    w_type = wop_obj.w_static_type
    if w_type is B.w_dynamic:
        return W_OpSpec(OP.w_dynamic_setattr)
    elif attr in w_type.spy_members:
        return opspec_member('set', vm, w_type, attr)
    elif w_SETATTR := w_type.lookup_blue_func('__SETATTR__'):
        return op_fast_call(vm, w_SETATTR, [wop_obj, wop_attr, wop_v])
    elif w_setattr := w_type.lookup_func('__setattr__'):
        return W_OpSpec(w_setattr, [wop_obj, wop_attr, wop_v])
    return W_OpSpec.NULL


def opspec_member(kind: OpKind, vm: 'SPyVM', w_type: W_Type,
                  attr: str) -> W_OpSpec:
    member = w_type.spy_members[attr]
    field = member.field # the interp-level name of the attr (e.g, 'w_x')
    T = Annotated[W_Object, w_type]        # type of the object
    V = Annotated[W_Object, member.w_type] # type of the attribute

    if kind == 'get':
        @builtin_func(w_type.fqn, f"__get_{attr}__")
        def w_opimpl_get(vm: 'SPyVM', w_obj: T, w_attr: W_Str) -> V:
            return getattr(w_obj, field)

        return W_OpSpec(w_opimpl_get)

    elif kind == 'set':
        @builtin_func(w_type.fqn, f"__set_{attr}__")
        def w_opimpl_set(vm: 'SPyVM', w_obj: T, w_attr: W_Str, w_val: V)-> None:
            setattr(w_obj, field, w_val)

        return W_OpSpec(w_opimpl_set)

    else:
        assert False, f'Invalid OpKind: {kind}'
