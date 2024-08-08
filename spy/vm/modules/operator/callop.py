from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type, W_Dynamic
from spy.vm.str import W_Str
from spy.vm.opimpl import W_OpImpl

from . import OP
from .binop import MM
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@OP.builtin(color='blue')
def CALL(vm: 'SPyVM', w_type: W_Type, w_argtypes: W_Object) -> W_OpImpl:
    pyclass = w_type.pyclass
    if w_type is B.w_dynamic:
        raise NotImplementedError("implement me")
    elif pyclass.has_meth_overriden('op_CALL'):
        return pyclass.op_CALL(vm, w_type, w_argtypes)
    return W_OpImpl.NULL

@OP.builtin(color='blue')
def CALL_METHOD(vm: 'SPyVM', w_type: W_Type, w_method: W_Str,
                w_argtypes: W_Object) -> W_OpImpl:
    pyclass = w_type.pyclass
    if pyclass.has_meth_overriden('op_CALL_METHOD'):
        return pyclass.op_CALL_METHOD(vm, w_type, w_method, w_argtypes)
    return W_OpImpl.NULL
