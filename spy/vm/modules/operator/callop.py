from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type, W_Dynamic
from spy.vm.str import W_Str
from spy.vm.opimpl import W_OpImpl, W_Value
from spy.vm.list import W_List

from . import OP
from .binop import MM
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

W_List.make_prebuilt(W_Value)

@OP.builtin(color='blue')
def CALL(vm: 'SPyVM', wv_obj: W_Value, w_values: W_List[W_Value]) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opimpl
    w_opimpl = W_OpImpl.NULL
    w_type = wv_obj.w_static_type
    pyclass = w_type.pyclass
    if w_type is B.w_dynamic:
        raise NotImplementedError("implement me")
    elif pyclass.has_meth_overriden('op_CALL'):
        w_opimpl = pyclass.op_CALL(vm, wv_obj, w_values)

    # turn the app-level W_List[W_Value] into an interp-level list[W_Value]
    args_wv = w_values.items_w
    typecheck_opimpl(
        vm,
        w_opimpl,
        [wv_obj] + args_wv,
        dispatch = 'single',
        errmsg = 'cannot call objects of type `{0}`'
    )
    return w_opimpl

@OP.builtin(color='blue')
def CALL_METHOD(vm: 'SPyVM', wv_obj: W_Value, wv_method: W_Value,
                w_values: W_List[W_Value]) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opimpl
    w_opimpl = W_OpImpl.NULL
    w_type = wv_obj.w_static_type
    pyclass = w_type.pyclass
    if pyclass.has_meth_overriden('op_CALL_METHOD'):
        w_opimpl = pyclass.op_CALL_METHOD(vm, wv_obj, wv_method, w_values)

    # turn the app-level W_List[W_Value] into an interp-level list[W_Value]
    args_wv = w_values.items_w
    typecheck_opimpl(
        vm,
        w_opimpl,
        [wv_obj, wv_method] + args_wv,
        dispatch = 'single',
        errmsg = 'cannot call methods on type `{0}`'
    )
    return w_opimpl
