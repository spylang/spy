from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type, W_Dynamic
from spy.vm.str import W_Str
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.list import W_List
from spy.vm.function import W_DirectCall, W_FuncType, FuncParam

from . import OP
from .binop import MM
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

W_List.make_prebuilt(W_OpArg)

@OP.builtin(color='blue')
def CALL(vm: 'SPyVM', wv_obj: W_OpArg, w_values: W_List[W_OpArg]) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opimpl
    w_opimpl = W_OpImpl.NULL
    w_type = wv_obj.w_static_type
    pyclass = w_type.pyclass
    if w_type is B.w_dynamic:
        w_opimpl = _dynamic_call_opimpl(w_values.items_w)
    elif pyclass.has_meth_overriden('op_CALL'):
        w_opimpl = pyclass.op_CALL(vm, wv_obj, w_values)

    # turn the app-level W_List[W_OpArg] into an interp-level list[W_OpArg]
    args_wv = w_values.items_w
    typecheck_opimpl(
        vm,
        w_opimpl,
        [wv_obj] + args_wv,
        dispatch = 'single',
        errmsg = 'cannot call objects of type `{0}`'
    )
    return w_opimpl


def _dynamic_call_opimpl(args_wv: list[W_OpArg]) -> W_OpImpl:
    """
    This is a hack, and it's half wrong.

    We are trying to CALL something of type dynamic, so we don't know anything
    about it. Ideally, we would like a setup like this:

    in opimpl_dynamic.py:
        def dynamic_call(vm, w_obj: W_Dynamic, args_w: list[W_Dynamic])

    here:
        return W_OpImpl.simple(OP.w_dynamic_call)

    but this doesn't work because we don't have any support for calling
    opimpls with a variable number of arguments.

    The temporary workaround is to pretend that this is a direct call: for
    this, we fabricate a fake w_functype which takes the right number of
    arguments, to ensure that we pass the typechecking.

    The half-right part is that this works well if the dynamic object turns
    out to be actually a W_Func, and no type conversions are necessary.
    The half-wrong part is that this breaks in all other cases, but for now
    it's good enough.
    """
    N  = len(args_wv)
    w_functype = W_FuncType(
        params = [FuncParam(f'v{i}', B.w_dynamic) for i in range(N)],
        w_restype = B.w_dynamic
    )
    return W_OpImpl.with_values(
        W_DirectCall(w_functype),
        args_wv
    )


@OP.builtin(color='blue')
def CALL_METHOD(vm: 'SPyVM', wv_obj: W_OpArg, wv_method: W_OpArg,
                w_values: W_List[W_OpArg]) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opimpl
    w_opimpl = W_OpImpl.NULL
    w_type = wv_obj.w_static_type
    pyclass = w_type.pyclass
    if pyclass.has_meth_overriden('op_CALL_METHOD'):
        w_opimpl = pyclass.op_CALL_METHOD(vm, wv_obj, wv_method, w_values)

    # turn the app-level W_List[W_OpArg] into an interp-level list[W_OpArg]
    args_wv = w_values.items_w
    typecheck_opimpl(
        vm,
        w_opimpl,
        [wv_obj, wv_method] + args_wv,
        dispatch = 'single',
        errmsg = 'cannot call methods on type `{0}`'
    )
    return w_opimpl
