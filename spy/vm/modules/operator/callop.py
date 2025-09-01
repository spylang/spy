from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.opspec import W_OpSpec, W_MetaArg
from spy.vm.opimpl import W_OpImpl
from spy.vm.function import W_FuncType, W_Func

from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin_func(color='blue')
def w_CALL(vm: 'SPyVM', wm_obj: W_MetaArg, *args_wm: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_opspec = W_OpSpec.NULL
    w_T = wm_obj.w_static_T

    newargs_wm = [wm_obj] + list(args_wm)
    errmsg = 'cannot call objects of type `{0}`'

    if isinstance(w_T, W_FuncType):
        # W_Func is a special case, as it can't have a w_CALL for bootstrapping
        # reasons. Moreover, while we are at it, we can produce a better error
        # message in case we try to call a plain function with [].
        assert w_T.pyclass is W_Func
        if w_T.kind == 'plain':
            w_opspec = W_Func.op_CALL(vm, wm_obj, *args_wm) # type: ignore
        elif w_T.kind == 'metafunc':
            assert w_T.pyclass is W_Func
            w_opspec = W_Func.op_METACALL(vm, wm_obj, *args_wm) # type: ignore
        elif w_T.kind == 'generic':
            errmsg = 'generic functions must be called via `[...]`'
        else:
            assert False, f'unknown FuncKind: {w_T.kind}'

    elif w_T is B.w_dynamic:
        w_opspec = W_OpSpec(OP.w_dynamic_call)
    elif w_call := w_T.lookup_func('__call__'):
        w_opspec = vm.fast_metacall(w_call, newargs_wm)

    return typecheck_opspec(
        vm,
        w_opspec,
        newargs_wm,
        dispatch = 'single',
        errmsg = errmsg,
    )


@OP.builtin_func(color='blue')
def w_CALL_METHOD(vm: 'SPyVM', wm_obj: W_MetaArg, wm_method: W_MetaArg,
                  *args_wm: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_opspec = W_OpSpec.NULL
    w_T = wm_obj.w_static_T

    # if the type provides __call_method__, use it
    if w_call_method := w_T.lookup_func('__call_method__'):
        newargs_wm = [wm_obj, wm_method] + list(args_wm)
        w_opspec = vm.fast_metacall(w_call_method, newargs_wm)

    # else, the default implementation is to look into the type dict
    # XXX: is it correct here to assume that we get a blue string?
    meth = wm_method.blue_unwrap_str(vm)

    if w_func := w_T.dict_w.get(meth):
        # XXX: this should be turned into a proper exception, but for now we
        # cannot even write a test because we don't any way to inject
        # non-methods in the type dict
        assert isinstance(w_func, W_Func)
        # call the w_func, passing wm_obj as the implicit self
        w_opspec = W_OpSpec(w_func, [wm_obj] + list(args_wm))

    return typecheck_opspec(
        vm,
        w_opspec,
        [wm_obj, wm_method] + list(args_wm),
        dispatch = 'single',
        errmsg = f'method `{{0}}::{meth}` does not exist'
    )
