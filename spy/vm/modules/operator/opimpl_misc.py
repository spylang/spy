from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Object, W_Void, W_Dynamic
from spy.vm.str import W_Str
from spy.vm.module import W_Module
from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin
def generic_getattr(vm: 'SPyVM', w_obj: W_Object, w_attr: W_Str) -> W_Dynamic:
    return w_obj.opimpl_getattr(vm, w_attr)

@OP.builtin
def generic_setattr(vm: 'SPyVM', w_obj: W_Object, w_attr: W_Str,
                    w_value: W_Object) -> W_Void:
    w_obj.opimpl_setattr(vm, w_attr, w_value)
    return B.w_None
