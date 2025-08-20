from typing import TYPE_CHECKING, Literal, Annotated, Optional
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type
from spy.vm.str import W_Str
from spy.vm.function import W_Func
from spy.vm.builtin import builtin_func
from spy.vm.opspec import W_OpSpec, W_OpArg
from spy.vm.opimpl import W_OpImpl

from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

OpKind = Literal['get', 'set']

def unwrap_name_maybe(vm: 'SPyVM', wop_name: W_OpArg) -> str:
    if wop_name.is_blue() and wop_name.w_static_type is B.w_str:
        return vm.unwrap_str(wop_name.w_blueval)
    else:
        return '<unknown>'

@OP.builtin_func(color='blue')
def w_GETATTR(vm: 'SPyVM', wop_obj: W_OpArg, wop_name: W_OpArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    name = unwrap_name_maybe(vm, wop_name)
    w_opspec = _get_GETATTR_opspec(vm, wop_obj, wop_name, name)
    return typecheck_opspec(
        vm,
        w_opspec,
        [wop_obj, wop_name],
        dispatch = 'single',
        errmsg = "type `{0}` has no attribute '%s'" % name
    )

def _get_GETATTR_opspec(vm: 'SPyVM', wop_obj: W_OpArg, wop_name: W_OpArg,
                        name: str) -> W_OpSpec:
    w_T = wop_obj.w_static_type

    if w_T is B.w_dynamic:
        return W_OpSpec(OP.w_dynamic_getattr)

    if w_getattribute := w_T.lookup_func(f'__getattribute__'):
        return vm.fast_metacall(w_getattribute, [wop_obj, wop_name])


    # this is more or less the equivalent to object.__getattribute__, with a
    # big difference: in Python, obj.__dict__ has precedence over
    # type(obj).__dict__. In SPy, it's the opposite, because we want to be
    # able to do attribute/method resolution on the static type (and thus
    # obj.__dict__ is completely unknown).
    #
    # The nice result is that the logic is much simpler now, because we don't
    # have to worry about data/non-data descriptors.
    elif w_val := w_T.lookup(name):
        w_val_type = vm.dynamic_type(w_val)
        w_get = w_val_type.lookup_func('__get__')
        if w_get:
            # w_val is a descriptor! We can call its __get__
            wop_member = W_OpArg.from_w_obj(vm, w_val)
            return vm.fast_metacall(w_get, [wop_member, wop_obj])
        else:
            return W_OpSpec.const(w_val)

    return W_OpSpec.NULL


@OP.builtin_func(color='blue')
def w_SETATTR(vm: 'SPyVM', wop_obj: W_OpArg, wop_name: W_OpArg,
            wop_v: W_OpArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    name = unwrap_name_maybe(vm, wop_name)
    w_opspec = _get_SETATTR_opspec(vm, wop_obj, wop_name, wop_v, name)
    errmsg = "type `{0}` does not support assignment to attribute '%s'" % name
    return typecheck_opspec(
        vm,
        w_opspec,
        [wop_obj, wop_name, wop_v],
        dispatch = 'single',
        errmsg = errmsg
    )

def _get_SETATTR_opspec(vm: 'SPyVM', wop_obj: W_OpArg, wop_name: W_OpArg,
                        wop_v: W_OpArg, name: str) -> W_OpSpec:
    w_type = wop_obj.w_static_type

    if w_type is B.w_dynamic:
        return W_OpSpec(OP.w_dynamic_setattr)

    # try to find a descriptor with a __set__ method
    elif w_member := w_type.lookup(name):
        w_member_type = vm.dynamic_type(w_member)
        w_set = w_member_type.lookup_func('__set__')
        if w_set:
            # w_member is a descriptor! We can call its __set__
            wop_member = W_OpArg.from_w_obj(vm, w_member)
            return vm.fast_metacall(w_set, [wop_member, wop_obj, wop_v])

    elif w_setattr := w_type.lookup_func('__setattr__'):
        return vm.fast_metacall(w_setattr, [wop_obj, wop_name, wop_v])

    return W_OpSpec.NULL
