from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Object
from spy.vm.str import W_Str
from spy.vm.module import W_Module
from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.primitive('def(obj: object, attr: str) -> dynamic')
def generic_getattr(vm: 'SPyVM', w_obj: W_Object, w_attr: W_Str) -> W_Object:
    return w_obj.getattr_impl(vm, w_attr)

@OP.primitive('def(obj: object, attr: str, v: object) -> void')
def generic_setattr(vm: 'SPyVM', w_obj: W_Object, w_attr: W_Str,
                    w_value: W_Object) -> None:
    w_obj.setattr_impl(vm, w_attr, w_value)
