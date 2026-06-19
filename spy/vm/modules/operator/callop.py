from typing import TYPE_CHECKING

from spy.vm.b import B
from spy.vm.function import W_Func, W_FuncArgs, W_FuncType
from spy.vm.modules.operator.attrop import unwrap_name_maybe
from spy.vm.opimpl import W_OpImpl
from spy.vm.opspec import W_MetaArg, W_OpSpec

from . import OP

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin_func(color="blue")
def w_CALL(vm: "SPyVM", wam_obj: W_MetaArg, wam_funcargs: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec

    w_opspec = W_OpSpec.NULL
    w_T = wam_obj.w_static_T

    w_funcargs = wam_funcargs.w_blueval
    assert isinstance(w_funcargs, W_FuncArgs)
    newargs_wam = [wam_obj] + w_funcargs.to_list()
    errmsg = "cannot call objects of type `{0}`"

    if isinstance(w_T, W_FuncType):
        # W_Func is a special case, as it can't have a w_CALL for bootstrapping
        # reasons. Moreover, while we are at it, we can produce a better error
        # message in case we try to call a plain function with [].
        assert w_T.pyclass is W_Func
        if w_T.kind == "plain":
            w_opspec = W_Func.op_CALL(vm, wam_obj, wam_funcargs)
        elif w_T.kind == "metafunc":
            assert w_T.pyclass is W_Func
            w_opspec = W_Func.op_METACALL(vm, wam_obj, wam_funcargs)
        elif w_T.kind == "generic":
            errmsg = "generic functions must be called via `[...]`"
        else:
            assert False, f"unknown FuncKind: {w_T.kind}"

    elif w_T is B.w_dynamic:
        if w_funcargs.kwargs_wam:
            errmsg = "keyword arguments not supported for this function"
        else:
            w_opspec = W_OpSpec(OP.w_dynamic_call)
    elif w_call := w_T.lookup_func(vm, "__call__"):
        if w_funcargs.kwargs_wam:
            errmsg = "keyword arguments not supported for this function"
        else:
            w_opspec = vm.fast_metacall(w_call, newargs_wam)

    return typecheck_opspec(
        vm,
        w_opspec,
        newargs_wam,
        dispatch="single",
        errmsg=errmsg,
    )


@OP.builtin_func(color="blue")
def w_CALL_METHOD(
    vm: "SPyVM", wam_obj: W_MetaArg, wam_meth: W_MetaArg, wam_funcargs: W_MetaArg
) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec

    w_opspec = W_OpSpec.NULL
    w_T = wam_obj.w_static_T
    meth = unwrap_name_maybe(vm, wam_meth)
    errmsg = f"method `{{0}}::{meth}` does not exist"

    w_funcargs = wam_funcargs.w_blueval
    assert isinstance(w_funcargs, W_FuncArgs)
    newargs_wam = [wam_obj, wam_meth] + w_funcargs.to_list()

    # if the type provides __call_method__, use it
    if w_call_method := w_T.lookup_func(vm, "__call_method__"):
        if w_funcargs.kwargs_wam:
            errmsg = "keyword arguments not supported for this function"
        else:
            w_opspec = vm.fast_metacall(w_call_method, newargs_wam)
    else:
        w_opspec = default_callmethod(vm, wam_obj, wam_meth, w_funcargs, meth)

    return typecheck_opspec(
        vm,
        w_opspec,
        newargs_wam,
        dispatch="single",
        errmsg=errmsg,
    )


def default_callmethod(
    vm: "SPyVM",
    wam_obj: W_MetaArg,
    wam_meth: W_MetaArg,
    w_funcargs: W_FuncArgs,
    meth: str,
) -> W_OpSpec:
    """
    Default logic for call_method: look into the type dict
    """
    w_T = wam_obj.w_static_T
    if w_func := w_T.lookup(vm, meth):
        # XXX: this should be turned into a proper exception, but for now we
        # cannot even write a test because we don't any way to inject
        # non-methods in the type dict
        assert isinstance(w_func, W_Func)
        wam_func = W_MetaArg.from_w_obj(vm, w_func, color="blue")
        # prepend self to args
        new_funcargs = W_FuncArgs(
            [wam_obj] + w_funcargs.args_wam,
            w_funcargs.kwargs_wam,
        )
        wam_new_funcargs = W_MetaArg.from_w_obj(vm, new_funcargs, loc=wam_obj.loc)

        kind = w_func.w_functype.kind
        if kind == "plain":
            return W_Func.op_CALL(vm, wam_func, wam_new_funcargs)
        elif kind == "metafunc":
            return W_Func.op_METACALL(vm, wam_func, wam_new_funcargs)
        else:
            return W_OpSpec.NULL

    else:
        return W_OpSpec.NULL
