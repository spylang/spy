from typing import TYPE_CHECKING, Any
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type, W_i32, W_bool
from . import OPS
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

# the following style is a bit too verbose. We could greatly reduce code
# duplication by using some metaprogramming, but it might become too
# magic. Or, it would be nice to have automatic unwrapping.
# Let's to the dumb&verbose thing for now

def _i32_op(vm: 'SPyVM', w_a: W_Object, w_b: W_Object, fn: Any) -> Any:
    a = vm.unwrap_i32(w_a)
    b = vm.unwrap_i32(w_b)
    res = fn(a, b)
    return vm.wrap(res)

@OPS.primitive('def(a: i32, b: i32) -> i32')
def i32_add(vm: 'SPyVM', w_a: W_i32, w_b: W_i32) -> W_i32:
    return _i32_op(vm, w_a, w_b, lambda a, b: a + b)

@OPS.primitive('def(a: i32, b: i32) -> i32')
def i32_mul(vm: 'SPyVM', w_a: W_i32, w_b: W_i32) -> W_i32:
    return _i32_op(vm, w_a, w_b, lambda a, b: a * b)

@OPS.primitive('def(a: i32, b: i32) -> bool')
def i32_eq(vm: 'SPyVM', w_a: W_i32, w_b: W_i32) -> W_bool:
    return _i32_op(vm, w_a, w_b, lambda a, b: a == b)

@OPS.primitive('def(a: i32, b: i32) -> bool')
def i32_ne(vm: 'SPyVM', w_a: W_i32, w_b: W_i32) -> W_bool:
    return _i32_op(vm, w_a, w_b, lambda a, b: a != b)

@OPS.primitive('def(a: i32, b: i32) -> bool')
def i32_lt(vm: 'SPyVM', w_a: W_i32, w_b: W_i32) -> W_bool:
    return _i32_op(vm, w_a, w_b, lambda a, b: a < b)

@OPS.primitive('def(a: i32, b: i32) -> bool')
def i32_le(vm: 'SPyVM', w_a: W_i32, w_b: W_i32) -> W_bool:
    return _i32_op(vm, w_a, w_b, lambda a, b: a <= b)

@OPS.primitive('def(a: i32, b: i32) -> bool')
def i32_gt(vm: 'SPyVM', w_a: W_i32, w_b: W_i32) -> W_bool:
    return _i32_op(vm, w_a, w_b, lambda a, b: a > b)

@OPS.primitive('def(a: i32, b: i32) -> bool')
def i32_ge(vm: 'SPyVM', w_a: W_i32, w_b: W_i32) -> W_bool:
    return _i32_op(vm, w_a, w_b, lambda a, b: a >= b)
