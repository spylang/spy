from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Object
from spy.vm.str import W_Str
from spy.vm.module import W_Module
from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.primitive('def(m: module, attr: str) -> dynamic')
def module_getattr(vm: 'SPyVM', w_mod: W_Module, w_attr: W_Str) -> W_Object:
    # XXX this is wrong: ideally, we should create a new subtype for each
    # module, where every member has its own static type.
    #
    # For now, we just use dynamic, which is good enough for now, since all
    # the module getattrs are done in blue contexts are redshifted away.
    attr = vm.unwrap_str(w_attr)
    return w_mod.getattr(attr)

@OP.primitive('def(m: module, attr: str, v: object) -> dynamic')
def module_setattr(vm: 'SPyVM', w_mod: W_Module, w_attr: W_Str,
                   w_value: W_Object) -> W_Object:
    attr = vm.unwrap_str(w_attr)
    w_mod.setattr(attr, w_value)
    return B.w_None


@OP.primitive('def(obj: object, attr: str) -> dynamic')
def generic_getattr(vm: 'SPyVM', w_obj: W_Object, w_attr: W_Str) -> W_Object:
    return w_obj.getattr_impl(vm, w_attr)

@OP.primitive('def(obj: object, attr: str, v: object) -> dynamic')
def generic_setattr(vm: 'SPyVM', w_obj: W_Object, w_attr: W_Str,
                    w_value: W_Object) -> W_Object:
    return w_obj.spy_setattr(vm, w_attr, w_value)
