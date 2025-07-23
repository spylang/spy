from typing import TYPE_CHECKING
from spy.vm.opspec import W_OpSpec, W_OpArg
from spy.vm.opimpl import W_OpImpl
from spy.vm.function import W_FuncType

from . import OP, op_fast_call
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin_func(color='blue')
def w_GETITEM(vm: 'SPyVM', wop_obj: W_OpArg, *args_wop: W_OpArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_opimpl = W_OpSpec.NULL
    w_type = wop_obj.w_static_type

    newargs_wop = [wop_obj] + list(args_wop)
    if isinstance(w_type, W_FuncType) and w_type.kind == 'generic':
        # special case: for generic W_Funcs, "[]" means "call"
        w_opimpl = w_type.pyclass.op_CALL(vm, wop_obj, *args_wop) # type: ignore
    elif w_GETITEM := w_type.lookup_blue_func('__GETITEM__'):
        w_opimpl = op_fast_call(vm, w_GETITEM, newargs_wop)
    elif w_getitem := w_type.lookup_func('__getitem__'):
        w_opimpl = W_OpSpec(w_getitem, newargs_wop)

    return typecheck_opspec(
        vm,
        w_opimpl,
        newargs_wop,
        dispatch = 'single',
        errmsg = 'cannot do `{0}`[...]'
    )


@OP.builtin_func(color='blue')
def w_SETITEM(vm: 'SPyVM', wop_obj: W_OpArg, *args_wop: W_OpArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_opimpl = W_OpSpec.NULL
    w_type = wop_obj.w_static_type

    newargs_wop = [wop_obj] + list(args_wop)
    if w_SETITEM := w_type.lookup_blue_func('__SETITEM__'):
        w_opimpl = op_fast_call(vm, w_SETITEM, newargs_wop)
    elif w_setitem := w_type.lookup_func('__setitem__'):
        w_opimpl = W_OpSpec(w_setitem, newargs_wop)

    return typecheck_opspec(
        vm,
        w_opimpl,
        newargs_wop,
        dispatch = 'single',
        errmsg = "cannot do `{0}[`{1}`] = ..."
    )
