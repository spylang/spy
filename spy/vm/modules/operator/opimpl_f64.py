from typing import TYPE_CHECKING, Any
from spy.vm.object import W_Object
from spy.vm.primitive import W_F64, W_Bool
from spy.errors import SPyError
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

def _f64_unary_op(vm: 'SPyVM', w_a: W_Object, fn: Any) -> Any:
    a = vm.unwrap_f64(w_a)
    res = fn(a)
    return vm.wrap(res)

@OP.builtin_func
def w_f64_add(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_F64:
    return _f64_op(vm, w_a, w_b, lambda a, b: a + b)

@OP.builtin_func
def w_f64_sub(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_F64:
    return _f64_op(vm, w_a, w_b, lambda a, b: a - b)

@OP.builtin_func
def w_f64_mul(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_F64:
    return _f64_op(vm, w_a, w_b, lambda a, b: a * b)

@OP.builtin_func
def w_f64_div(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_F64:
    if w_b.value == 0:
        raise SPyError("W_ZeroDivisionError", "float division by zero")
    return _f64_op(vm, w_a, w_b, lambda a, b: a / b)

@OP.builtin_func
def w_f64_floordiv(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_F64:
    if w_b.value == 0:
        raise SPyError("W_ZeroDivisionError", "float floor division by zero")
    return _f64_op(vm, w_a, w_b, lambda a, b: a // b)

@OP.builtin_func
def w_f64_mod(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_F64:
    if w_b.value == 0:
        raise SPyError("W_ZeroDivisionError", "float modulo by zero")
    return _f64_op(vm, w_a, w_b, lambda a, b: a % b)

@OP.builtin_func
def w_f64_eq(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_Bool:
    return _f64_op(vm, w_a, w_b, lambda a, b: a == b)

@OP.builtin_func
def w_f64_ne(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_Bool:
    return _f64_op(vm, w_a, w_b, lambda a, b: a != b)

@OP.builtin_func
def w_f64_lt(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_Bool:
    return _f64_op(vm, w_a, w_b, lambda a, b: a < b)

@OP.builtin_func
def w_f64_le(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_Bool:
    return _f64_op(vm, w_a, w_b, lambda a, b: a <= b)

@OP.builtin_func
def w_f64_gt(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_Bool:
    return _f64_op(vm, w_a, w_b, lambda a, b: a > b)

@OP.builtin_func
def w_f64_ge(vm: 'SPyVM', w_a: W_F64, w_b: W_F64) -> W_Bool:
    return _f64_op(vm, w_a, w_b, lambda a, b: a >= b)

@OP.builtin_func
def w_f64_neg(vm: 'SPyVM', w_a: W_F64) -> W_F64:
    return _f64_unary_op(vm, w_a, lambda a: -a)
