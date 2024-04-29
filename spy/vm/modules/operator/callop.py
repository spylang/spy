from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type, W_Dynamic

from . import OP
from .binop import MM
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@OP.builtin
def CALL(vm: 'SPyVM', w_type: W_Type, w_argtypes: W_Object) -> W_Dynamic:
    pyclass = w_type.pyclass
    if w_type is B.w_dynamic:
        raise NotImplementedError("implement me")
    elif pyclass.has_meth_overriden('op_CALL'):
        return pyclass.op_CALL(vm, w_type, w_argtypes)
    return B.w_NotImplemented
