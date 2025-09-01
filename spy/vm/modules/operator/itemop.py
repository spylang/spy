from typing import TYPE_CHECKING
from spy.vm.opspec import W_OpSpec, W_MetaArg
from spy.vm.opimpl import W_OpImpl
from spy.vm.function import W_FuncType

from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin_func(color='blue')
def w_GETITEM(vm: 'SPyVM', wm_obj: W_MetaArg, *args_wm: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_opspec = W_OpSpec.NULL
    w_T = wm_obj.w_static_T

    newargs_wm = [wm_obj] + list(args_wm)
    if isinstance(w_T, W_FuncType) and w_T.kind == 'generic':
        # special case: for generic W_Funcs, "[]" means "call"
        w_opspec = w_T.pyclass.op_CALL(vm, wm_obj, *args_wm) # type: ignore
    elif w_getitem := w_T.lookup_func('__getitem__'):
        w_opspec = vm.fast_metacall(w_getitem, newargs_wm)

    return typecheck_opspec(
        vm,
        w_opspec,
        newargs_wm,
        dispatch = 'single',
        errmsg = 'cannot do `{0}`[...]'
    )


@OP.builtin_func(color='blue')
def w_SETITEM(vm: 'SPyVM', wm_obj: W_MetaArg, *args_wm: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_opspec = W_OpSpec.NULL
    w_T = wm_obj.w_static_T

    newargs_wm = [wm_obj] + list(args_wm)
    if w_setitem := w_T.lookup_func('__setitem__'):
        w_opspec = vm.fast_metacall(w_setitem, newargs_wm)

    return typecheck_opspec(
        vm,
        w_opspec,
        newargs_wm,
        dispatch = 'single',
        errmsg = "cannot do `{0}[`{1}`] = ..."
    )
