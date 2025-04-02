from typing import TYPE_CHECKING, Any
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type
from spy.vm.primitive import W_U8, W_F64, W_Bool
from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

# the following style is a bit too verbose. We could greatly reduce code
# duplication by using some metaprogramming, but it might become too
# magic. Or, it would be nice to have automatic unwrapping.
# Let's to the dumb&verbose thing for now

def _u8_op(vm: 'SPyVM', w_a: W_Object, w_b: W_Object, fn: Any) -> Any:
    a = vm.unwrap_u8(w_a)
    b = vm.unwrap_u8(w_b)
    res = fn(a, b)
    return vm.wrap(res)

def _u8_unary_op(vm: 'SPyVM', w_a: W_Object, fn: Any) -> Any:
    a = vm.unwrap_u8(w_a)
    res = fn(a)
    return vm.wrap(res)

@OP.builtin_func
def w_u8_add(vm: 'SPyVM', w_a: W_U8, w_b: W_U8) -> W_U8:
    return _u8_op(vm, w_a, w_b, lambda a, b: a + b)

@OP.builtin_func
def w_u8_sub(vm: 'SPyVM', w_a: W_U8, w_b: W_U8) -> W_U8:
    return _u8_op(vm, w_a, w_b, lambda a, b: a - b)

@OP.builtin_func
def w_u8_mul(vm: 'SPyVM', w_a: W_U8, w_b: W_U8) -> W_U8:
    return _u8_op(vm, w_a, w_b, lambda a, b: a * b)

@OP.builtin_func
def w_u8_div(vm: 'SPyVM', w_a: W_U8, w_b: W_U8) -> W_F64:
    return _u8_op(vm, w_a, w_b, lambda a, b: a / b)

@OP.builtin_func
def w_u8_floordiv(vm: 'SPyVM', w_a: W_U8, w_b: W_U8) -> W_U8:
    return _u8_op(vm, w_a, w_b, lambda a, b: a // b)

@OP.builtin_func
def w_u8_mod(vm: 'SPyVM', w_a: W_U8, w_b: W_U8) -> W_U8:
    return _u8_op(vm, w_a, w_b, lambda a, b: a % b)

@OP.builtin_func
def w_u8_lshift(vm: 'SPyVM', w_a: W_U8, w_b: W_U8) -> W_U8:
    return _u8_op(vm, w_a, w_b, lambda a, b: a << b)

@OP.builtin_func
def w_u8_rshift(vm: 'SPyVM', w_a: W_U8, w_b: W_U8) -> W_U8:
    return _u8_op(vm, w_a, w_b, lambda a, b: a >> b)

@OP.builtin_func
def w_u8_and(vm: 'SPyVM', w_a: W_U8, w_b: W_U8) -> W_U8:
    return _u8_op(vm, w_a, w_b, lambda a, b: a & b)

@OP.builtin_func
def w_u8_or(vm: 'SPyVM', w_a: W_U8, w_b: W_U8) -> W_U8:
    return _u8_op(vm, w_a, w_b, lambda a, b: a | b)

@OP.builtin_func
def w_u8_xor(vm: 'SPyVM', w_a: W_U8, w_b: W_U8) -> W_U8:
    return _u8_op(vm, w_a, w_b, lambda a, b: a ^ b)

@OP.builtin_func
def w_u8_eq(vm: 'SPyVM', w_a: W_U8, w_b: W_U8) -> W_Bool:
    return _u8_op(vm, w_a, w_b, lambda a, b: a == b)

@OP.builtin_func
def w_u8_ne(vm: 'SPyVM', w_a: W_U8, w_b: W_U8) -> W_Bool:
    return _u8_op(vm, w_a, w_b, lambda a, b: a != b)

@OP.builtin_func
def w_u8_lt(vm: 'SPyVM', w_a: W_U8, w_b: W_U8) -> W_Bool:
    return _u8_op(vm, w_a, w_b, lambda a, b: a < b)

@OP.builtin_func
def w_u8_le(vm: 'SPyVM', w_a: W_U8, w_b: W_U8) -> W_Bool:
    return _u8_op(vm, w_a, w_b, lambda a, b: a <= b)

@OP.builtin_func
def w_u8_gt(vm: 'SPyVM', w_a: W_U8, w_b: W_U8) -> W_Bool:
    return _u8_op(vm, w_a, w_b, lambda a, b: a > b)

@OP.builtin_func
def w_u8_ge(vm: 'SPyVM', w_a: W_U8, w_b: W_U8) -> W_Bool:
    return _u8_op(vm, w_a, w_b, lambda a, b: a >= b)

@OP.builtin_func
def w_u8_neg(vm: 'SPyVM', w_a: W_U8) -> W_U8:
    return _u8_unary_op(vm, w_a, lambda a: -a)
