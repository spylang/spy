from typing import TYPE_CHECKING

from spy.vm.function import W_FuncType
from spy.vm.opimpl import W_OpImpl
from spy.vm.opspec import W_MetaArg, W_OpSpec

from . import OP

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin_func(color="blue")
def w_GETITEM(vm: "SPyVM", wam_obj: W_MetaArg, *args_wam: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec

    w_opspec = W_OpSpec.NULL
    w_T = wam_obj.w_static_T

    newargs_wam = [wam_obj] + list(args_wam)
    if isinstance(w_T, W_FuncType) and w_T.kind == "generic":
        # special case: for generic W_Funcs, "[]" means "call"
        w_opspec = w_T.pyclass.op_CALL(vm, wam_obj, *args_wam)  # type: ignore
    elif w_getitem := w_T.lookup_func("__getitem__"):
        w_opspec = vm.fast_metacall(w_getitem, newargs_wam)

    return typecheck_opspec(
        vm, w_opspec, newargs_wam, dispatch="single", errmsg="cannot do `{0}`[...]"
    )


@OP.builtin_func(color="blue")
def w_SETITEM(vm: "SPyVM", wam_obj: W_MetaArg, *args_wam: W_MetaArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec

    w_opspec = W_OpSpec.NULL
    w_T = wam_obj.w_static_T

    newargs_wam = [wam_obj] + list(args_wam)
    if w_setitem := w_T.lookup_func("__setitem__"):
        w_opspec = vm.fast_metacall(w_setitem, newargs_wam)

    return typecheck_opspec(
        vm,
        w_opspec,
        newargs_wam,
        dispatch="single",
        errmsg="cannot do `{0}[`{1}`] = ...",
    )
