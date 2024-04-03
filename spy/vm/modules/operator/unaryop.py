from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type, W_Dynamic
from spy.vm.module import W_Module
from spy.vm.str import W_Str
from spy.vm.function import W_Func
from spy.vm.modules.types import W_TypeDef

from . import OP
from .binop import MM
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin
def GETITEM(vm: 'SPyVM', w_vtype: W_Type, w_itype: W_Type) -> W_Dynamic:
    return MM.lookup('[]', w_vtype, w_itype)


@OP.builtin
def GETATTR(vm: 'SPyVM', w_type: W_Type, w_attr: W_Str) -> W_Dynamic:
    pyclass = w_type.pyclass
    if w_type is B.w_dynamic:
        raise NotImplementedError("implement me")
    elif pyclass.has_meth_overriden('op_GETATTR'):
        return pyclass.op_GETATTR(vm, w_type, w_attr)

    # XXX refactor
    if isinstance(w_type, W_TypeDef) and w_type.w_getattr is not None:
        w_getattr = w_type.w_getattr
        assert isinstance(w_getattr, W_Func)
        w_opimpl = vm.call_function(w_getattr, [w_type, w_attr])
        return w_opimpl

    return B.w_NotImplemented


@OP.builtin
def SETATTR(vm: 'SPyVM', w_type: W_Type, w_attr: W_Str,
            w_vtype: W_Type) -> W_Dynamic:
    pyclass = w_type.pyclass
    if w_type is B.w_dynamic:
        return OP.w_dynamic_setattr
    elif pyclass.has_meth_overriden('op_SETATTR'):
        return pyclass.op_SETATTR(vm, w_type, w_attr, w_vtype)

    # XXX refactor
    if isinstance(w_type, W_TypeDef) and w_type.w_setattr is not None:
        w_setattr = w_type.w_setattr
        assert isinstance(w_setattr, W_Func)
        w_opimpl = vm.call_function(w_setattr, [w_type, w_attr, w_vtype])
        return w_opimpl

    return B.w_NotImplemented
