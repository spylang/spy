from typing import TYPE_CHECKING, Any
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type
from spy.vm.primitive import W_I32, W_Bool
from . import OP
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

@OP.builtin_func
def w_i32_add(vm: 'SPyVM', w_a: W_I32, w_b: W_I32) -> W_I32:
    return _i32_op(vm, w_a, w_b, lambda a, b: a + b)

@OP.builtin_func
def w_i32_sub(vm: 'SPyVM', w_a: W_I32, w_b: W_I32) -> W_I32:
    return _i32_op(vm, w_a, w_b, lambda a, b: a - b)

@OP.builtin_func
def w_i32_mul(vm: 'SPyVM', w_a: W_I32, w_b: W_I32) -> W_I32:
    return _i32_op(vm, w_a, w_b, lambda a, b: a * b)

# XXX: should we do floor division or float division?
@OP.builtin_func
def w_i32_div(vm: 'SPyVM', w_a: W_I32, w_b: W_I32) -> W_I32:
    return _i32_op(vm, w_a, w_b, lambda a, b: a // b)

@OP.builtin_func
def w_i32_mod(vm: 'SPyVM', w_a: W_I32, w_b: W_I32) -> W_I32:
    return _i32_op(vm, w_a, w_b, lambda a, b: a % b)

@OP.builtin_func
def w_i32_eq(vm: 'SPyVM', w_a: W_I32, w_b: W_I32) -> W_Bool:
    return _i32_op(vm, w_a, w_b, lambda a, b: a == b)

@OP.builtin_func
def w_i32_ne(vm: 'SPyVM', w_a: W_I32, w_b: W_I32) -> W_Bool:
    return _i32_op(vm, w_a, w_b, lambda a, b: a != b)

@OP.builtin_func
def w_i32_lt(vm: 'SPyVM', w_a: W_I32, w_b: W_I32) -> W_Bool:
    return _i32_op(vm, w_a, w_b, lambda a, b: a < b)

@OP.builtin_func
def w_i32_le(vm: 'SPyVM', w_a: W_I32, w_b: W_I32) -> W_Bool:
    return _i32_op(vm, w_a, w_b, lambda a, b: a <= b)

@OP.builtin_func
def w_i32_gt(vm: 'SPyVM', w_a: W_I32, w_b: W_I32) -> W_Bool:
    return _i32_op(vm, w_a, w_b, lambda a, b: a > b)

@OP.builtin_func
def w_i32_ge(vm: 'SPyVM', w_a: W_I32, w_b: W_I32) -> W_Bool:
    return _i32_op(vm, w_a, w_b, lambda a, b: a >= b)
