from typing import TYPE_CHECKING, Any
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type, W_F64, W_Bool
from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

# the following style is a bit too verbose. We could greatly reduce code
# duplication by using some metaprogramming, but it might become too
# magic. Or, it would be nice to have automatic unwrapping.
# Let's to the dumb&verbose thing for now

def _f64_op(vm: 'SPyVM', w_a: W_Object, w_b: W_Object, fn: Any) -> Any:
    a = vm.unwrap_f64(w_a)
    b = vm.unwrap_f64(w_b)
    res = fn(a, b)
    return vm.wrap(res)

@OP.primitive('def(a: f64, b: f64) -> f64')
def f64_add(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_F64:
    return _f64_op(vm, w_a, w_b, lambda a, b: a + b)

@OP.primitive('def(a: f64, b: f64) -> f64')
def f64_sub(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_F64:
    return _f64_op(vm, w_a, w_b, lambda a, b: a - b)

@OP.primitive('def(a: f64, b: f64) -> f64')
def f64_mul(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_F64:
    return _f64_op(vm, w_a, w_b, lambda a, b: a * b)

@OP.primitive('def(a: f64, b: f64) -> f64')
def f64_div(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_F64:
    return _f64_op(vm, w_a, w_b, lambda a, b: a / b)

@OP.primitive('def(a: f64, b: f64) -> bool')
def f64_eq(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_Bool:
    return _f64_op(vm, w_a, w_b, lambda a, b: a == b)

@OP.primitive('def(a: f64, b: f64) -> bool')
def f64_ne(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_Bool:
    return _f64_op(vm, w_a, w_b, lambda a, b: a != b)

@OP.primitive('def(a: f64, b: f64) -> bool')
def f64_lt(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_Bool:
    return _f64_op(vm, w_a, w_b, lambda a, b: a < b)

@OP.primitive('def(a: f64, b: f64) -> bool')
def f64_le(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_Bool:
    return _f64_op(vm, w_a, w_b, lambda a, b: a <= b)

@OP.primitive('def(a: f64, b: f64) -> bool')
def f64_gt(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_Bool:
    return _f64_op(vm, w_a, w_b, lambda a, b: a > b)

@OP.primitive('def(a: f64, b: f64) -> bool')
def f64_ge(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_Bool:
    return _f64_op(vm, w_a, w_b, lambda a, b: a >= b)
