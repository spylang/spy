from typing import TYPE_CHECKING, Literal, Annotated, Optional
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type
from spy.vm.str import W_Str
from spy.vm.function import W_Func
from spy.vm.opspec import W_OpSpec, W_MetaArg
from spy.vm.opimpl import W_OpImpl

from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

OpKind = Literal['get', 'set']

def unwrap_name_maybe(vm: 'SPyVM', wm_name: W_MetaArg) -> str:
    if wm_name.is_blue() and wm_name.w_static_T is B.w_str:
        return vm.unwrap_str(wm_name.w_blueval)
    else:
        return '<unknown>'

@OP.builtin_func(color='blue')
def w_GETATTR(vm: 'SPyVM', wm_obj: W_MetaArg, wm_name: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    name = unwrap_name_maybe(vm, wm_name)

    w_T = wm_obj.w_static_T
    if w_T is B.w_dynamic:
        w_opspec = W_OpSpec(OP.w_dynamic_getattr)
    elif w_getattribute := w_T.lookup_func(f'__getattribute__'):
        w_opspec = vm.fast_metacall(w_getattribute, [wm_obj, wm_name])
    else:
        w_opspec = default_getattribute(vm, wm_obj, wm_name, name)

    return typecheck_opspec(
        vm,
        w_opspec,
        [wm_obj, wm_name],
        dispatch = 'single',
        errmsg = "type `{0}` has no attribute '%s'" % name
    )


def default_getattribute(
    vm: 'SPyVM',
    wm_obj: W_MetaArg,
    wm_name: W_MetaArg,
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

    w_T = wm_obj.w_static_T
    if w_attr := w_T.lookup(name):
        if w_get := vm.dynamic_type(w_attr).lookup_func('__get__'):
            # 1. found a descriptor on the type
            wm_attr = W_MetaArg.from_w_obj(vm, w_attr)
            return vm.fast_metacall(w_get, [wm_attr, wm_obj])
        else:
            # 2. found a normal attribute on the type
            return W_OpSpec.const(w_attr)

    # 3. look inside obj.__dict__
    # IMPLEMENT ME

    # 4. AttributeError
    return W_OpSpec.NULL


@OP.builtin_func(color='blue')
def w_SETATTR(vm: 'SPyVM', wm_obj: W_MetaArg, wm_name: W_MetaArg,
            wm_v: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    name = unwrap_name_maybe(vm, wm_name)
    w_opspec = _get_SETATTR_opspec(vm, wm_obj, wm_name, wm_v, name)
    errmsg = "type `{0}` does not support assignment to attribute '%s'" % name
    return typecheck_opspec(
        vm,
        w_opspec,
        [wm_obj, wm_name, wm_v],
        dispatch = 'single',
        errmsg = errmsg
    )

def _get_SETATTR_opspec(vm: 'SPyVM', wm_obj: W_MetaArg, wm_name: W_MetaArg,
                        wm_v: W_MetaArg, name: str) -> W_OpSpec:
    w_T = wm_obj.w_static_T

    if w_T is B.w_dynamic:
        return W_OpSpec(OP.w_dynamic_setattr)

    # try to find a descriptor with a __set__ method
    elif w_member := w_T.lookup(name):
        w_member_T = vm.dynamic_type(w_member)
        w_set = w_member_T.lookup_func('__set__')
        if w_set:
            # w_member is a descriptor! We can call its __set__
            wm_member = W_MetaArg.from_w_obj(vm, w_member)
            return vm.fast_metacall(w_set, [wm_member, wm_obj, wm_v])

    elif w_setattr := w_T.lookup_func('__setattr__'):
        return vm.fast_metacall(w_setattr, [wm_obj, wm_name, wm_v])

    return W_OpSpec.NULL
