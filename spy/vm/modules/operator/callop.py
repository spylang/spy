from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.opspec import W_OpSpec, W_MetaArg
from spy.vm.opimpl import W_OpImpl
from spy.vm.function import W_FuncType, W_Func

from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin_func(color='blue')
def w_CALL(vm: 'SPyVM', wam_obj: W_MetaArg, *args_wam: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_opspec = W_OpSpec.NULL
    w_T = wam_obj.w_static_T

    newargs_wam = [wam_obj] + list(args_wam)
    errmsg = 'cannot call objects of type `{0}`'

    if isinstance(w_T, W_FuncType):
        # W_Func is a special case, as it can't have a w_CALL for bootstrapping
        # reasons. Moreover, while we are at it, we can produce a better error
        # message in case we try to call a plain function with [].
        assert w_T.pyclass is W_Func
        if w_T.kind == 'plain':
            w_opspec = W_Func.op_CALL(vm, wam_obj, *args_wam) # type: ignore
        elif w_T.kind == 'metafunc':
            assert w_T.pyclass is W_Func
            w_opspec = W_Func.op_METACALL(vm, wam_obj, *args_wam) # type: ignore
        elif w_T.kind == 'generic':
            errmsg = 'generic functions must be called via `[...]`'
        else:
            assert False, f'unknown FuncKind: {w_T.kind}'

    elif w_T is B.w_dynamic:
        w_opspec = W_OpSpec(OP.w_dynamic_call)
    elif w_call := w_T.lookup_func('__call__'):
        w_opspec = vm.fast_metacall(w_call, newargs_wam)

    return typecheck_opspec(
        vm,
        w_opspec,
        newargs_wam,
        dispatch = 'single',
        errmsg = errmsg,
    )


@OP.builtin_func(color='blue')
def w_CALL_METHOD(vm: 'SPyVM', wam_obj: W_MetaArg, wam_method: W_MetaArg,
                  *args_wam: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_opspec = W_OpSpec.NULL
    w_T = wam_obj.w_static_T

    # if the type provides __call_method__, use it
    if w_call_method := w_T.lookup_func('__call_method__'):
        newargs_wam = [wam_obj, wam_method] + list(args_wam)
        w_opspec = vm.fast_metacall(w_call_method, newargs_wam)

    # XXXXXX THIS SEEMS WRONG!?!?
    # if we call __call_method__ then we fallthrough here?

    # else, the default implementation is to look into the type dict
    # XXX: is it correct here to assume that we get a blue string?
    meth = wam_method.blue_unwrap_str(vm)

    if w_func := w_T.dict_w.get(meth):
        # XXX: this should be turned into a proper exception, but for now we
        # cannot even write a test because we don't any way to inject
        # non-methods in the type dict
        assert isinstance(w_func, W_Func)
        # call the w_func, passing wam_obj as the implicit self
        w_opspec = W_OpSpec(w_func, [wam_obj] + list(args_wam))

    return typecheck_opspec(
        vm,
        w_opspec,
        [wam_obj, wam_method] + list(args_wam),
        dispatch = 'single',
        errmsg = f'method `{{0}}::{meth}` does not exist'
    )
