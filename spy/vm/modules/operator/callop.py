from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type
from spy.vm.primitive import W_Dynamic
from spy.vm.str import W_Str
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.function import W_DirectCall, W_FuncType, FuncParam, W_Func

from . import OP
from .binop import MM
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin_func(color='blue')
def w_CALL(vm: 'SPyVM', wop_obj: W_OpArg, *args_wop: W_OpArg) -> W_Func:
    from spy.vm.typechecker import typecheck_opimpl
    w_opimpl = W_OpImpl.NULL
    w_type = wop_obj.w_static_type
    pyclass = w_type.pyclass
    if w_type is B.w_dynamic:
        w_opimpl = W_OpImpl(OP.w_dynamic_call)
    elif pyclass.has_meth_overriden('op_CALL'):
        w_opimpl = pyclass.op_CALL(vm, wop_obj, *args_wop)

    return typecheck_opimpl(
        vm,
        w_opimpl,
        [wop_obj] + list(args_wop),
        dispatch = 'single',
        errmsg = 'cannot call objects of type `{0}`'
    )



@OP.builtin_func(color='blue')
def w_CALL_METHOD(vm: 'SPyVM', wop_obj: W_OpArg, wop_method: W_OpArg,
                  *args_wop: W_OpArg) -> W_Func:
    from spy.vm.typechecker import typecheck_opimpl
    w_opimpl = W_OpImpl.NULL
    w_type = wop_obj.w_static_type
    pyclass = w_type.pyclass
    if pyclass.has_meth_overriden('op_CALL_METHOD'):
        w_opimpl = pyclass.op_CALL_METHOD(vm, wop_obj, wop_method, *args_wop)

    return typecheck_opimpl(
        vm,
        w_opimpl,
        [wop_obj, wop_method] + list(args_wop),
        dispatch = 'single',
        errmsg = 'cannot call methods on type `{0}`'
    )
