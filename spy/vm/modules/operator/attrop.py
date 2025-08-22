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

    w_T = wop_obj.w_static_type
    if w_T is B.w_dynamic:
        w_opspec = W_OpSpec(OP.w_dynamic_getattr)
    elif w_getattribute := w_T.lookup_func(f'__getattribute__'):
        w_opspec = vm.fast_metacall(w_getattribute, [wop_obj, wop_name])
    else:
        w_opspec = default_getattribute(vm, wop_obj, wop_name, name)

    return typecheck_opspec(
        vm,
        w_opspec,
        [wop_obj, wop_name],
        dispatch = 'single',
        errmsg = "type `{0}` has no attribute '%s'" % name
    )


def default_getattribute(
    vm: 'SPyVM',
    wop_obj: W_OpArg,
    wop_name: W_OpArg,
    name: str
) -> W_OpSpec:
    # default logic for objects which don't implement __getattribute__. This
    # is the equivalent of CPython's object.c:PyObject_GenericGetAttr, and
    # corresponds more or less to object.__getattribute__.
    #
    # There is a big difference compared to Python, though.
    #   <python>
    #     1. try to find a data descriptor on the type
    #     2. try to look inside obj.__dict__
    #     3. try to find a non-data descriptor on the type
    #     4. try to find a normal attribute on the type
    #     5. AttributeError
    #   </python>
    #
    # This means that e.g. an instance can override methods via its __dict__.
    #
    # The SPy logic must be different, because we want to be able to resolve
    # the getattribute during redshift: in particular, during redshift we know
    # the static types but we DO NOT know the content of obj.__dict__ (if obj
    # is red). So, we tweak the logic:
    #   <spy>
    #     1. try to find a descriptor on the type
    #     2. try to find a normal attribute on the type
    #     3. try to look inside obj.__dict__ (if present)
    #     4. AttributeError
    #   </spy>
    #
    # This means that individual instances can NEVER override attributes
    # provided by their type. This also means that we no longer need the
    # distinction between data and non-data descriptors (as all descriptors
    # have the precedence anyway).
    #
    # Also note that contrarily to Python, in SPy instances don't have a
    # __dict__ by default. (__dict__ support not implemented yet ATM).

    w_T = wop_obj.w_static_type
    if w_attr := w_T.lookup(name):
        if w_get := vm.dynamic_type(w_attr).lookup_func('__get__'):
            # 1. found a descriptor on the type
            wop_attr = W_OpArg.from_w_obj(vm, w_attr)
            return vm.fast_metacall(w_get, [wop_attr, wop_obj])
        else:
            # 2. found a normal attribute on the type
            return W_OpSpec.const(w_attr)

    # 3. look inside obj.__dict__
    # IMPLEMENT ME

    # 4. AttributeError
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
    w_T = wop_obj.w_static_type

    if w_T is B.w_dynamic:
        return W_OpSpec(OP.w_dynamic_setattr)

    # try to find a descriptor with a __set__ method
    elif w_member := w_T.lookup(name):
        w_member_type = vm.dynamic_type(w_member)
        w_set = w_member_type.lookup_func('__set__')
        if w_set:
            # w_member is a descriptor! We can call its __set__
            wop_member = W_OpArg.from_w_obj(vm, w_member)
            return vm.fast_metacall(w_set, [wop_member, wop_obj, wop_v])

    elif w_setattr := w_T.lookup_func('__setattr__'):
        return vm.fast_metacall(w_setattr, [wop_obj, wop_name, wop_v])

    return W_OpSpec.NULL
