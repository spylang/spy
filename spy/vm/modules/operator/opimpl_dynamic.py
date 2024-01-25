from typing import TYPE_CHECKING, Any
from spy.errors import SPyTypeError
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type, W_i32, W_bool
from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@OP.primitive('def(a: dynamic, b: dynamic) -> dynamic')
def dynamic_add(vm: 'SPyVM', w_a: W_Object, w_b: W_Object) -> W_Object:
    w_ltype = vm.dynamic_type(w_a)
    w_rtype = vm.dynamic_type(w_b)
    w_opimpl = vm.call_function(OP.w_ADD, [w_ltype, w_rtype])
    if w_opimpl is B.w_NotImplemented:
        raise SPyTypeError(f'cannot do `{w_ltype.name}` + `{w_rtype.name}`')
    return vm.call_function(w_opimpl, [w_a, w_b])
