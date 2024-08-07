from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Type, W_Dynamic
from spy.vm.opimpl import W_OpImpl

from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin(color='blue')
def GETITEM(vm: 'SPyVM', w_type: W_Type, w_itype: W_Type) -> W_OpImpl:
    pyclass = w_type.pyclass
    if pyclass.has_meth_overriden('op_GETITEM'):
        return pyclass.op_GETITEM(vm, w_type, w_itype)

    return W_OpImpl.NULL

@OP.builtin(color='blue')
def SETITEM(vm: 'SPyVM', w_type: W_Type, w_itype: W_Type,
            w_vtype: W_Type) -> W_Dynamic:
    pyclass = w_type.pyclass
    if pyclass.has_meth_overriden('op_SETITEM'):
        return pyclass.op_SETITEM(vm, w_type, w_itype, w_vtype)

    return W_OpImpl.NULL
