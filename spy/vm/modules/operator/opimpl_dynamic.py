from typing import TYPE_CHECKING, Any
from spy.errors import SPyTypeError
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type, W_i32, W_bool
from spy.vm.function import W_Func
from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

def _dynamic_op(vm: 'SPyVM', w_op: W_Func,
                w_a: W_Object, w_b: W_Object,
                ) -> W_Object:
    w_ltype = vm.dynamic_type(w_a)
    w_rtype = vm.dynamic_type(w_b)
    w_opimpl = vm.call_function(w_op, [w_ltype, w_rtype])
    if w_opimpl is B.w_NotImplemented:
        token = OP.to_token(w_op)
        l = w_ltype.name
        r = w_rtype.name
        raise SPyTypeError(f'cannot do `{l}` {token} `{r}`')
    return vm.call_function(w_opimpl, [w_a, w_b])


@OP.primitive('def(a: dynamic, b: dynamic) -> dynamic')
def dynamic_add(vm: 'SPyVM', w_a: W_Object, w_b: W_Object) -> W_Object:
    return _dynamic_op(vm, OP.w_ADD, w_a, w_b)

@OP.primitive('def(a: dynamic, b: dynamic) -> dynamic')
def dynamic_mul(vm: 'SPyVM', w_a: W_Object, w_b: W_Object) -> W_Object:
    return _dynamic_op(vm, OP.w_MUL, w_a, w_b)

@OP.primitive('def(a: dynamic, b: dynamic) -> dynamic')
def dynamic_eq(vm: 'SPyVM', w_a: W_Object, w_b: W_Object) -> W_Object:
    return _dynamic_op(vm, OP.w_EQ, w_a, w_b)

@OP.primitive('def(a: dynamic, b: dynamic) -> dynamic')
def dynamic_ne(vm: 'SPyVM', w_a: W_Object, w_b: W_Object) -> W_Object:
    return _dynamic_op(vm, OP.w_NE, w_a, w_b)

@OP.primitive('def(a: dynamic, b: dynamic) -> dynamic')
def dynamic_lt(vm: 'SPyVM', w_a: W_Object, w_b: W_Object) -> W_Object:
    return _dynamic_op(vm, OP.w_LT, w_a, w_b)

@OP.primitive('def(a: dynamic, b: dynamic) -> dynamic')
def dynamic_le(vm: 'SPyVM', w_a: W_Object, w_b: W_Object) -> W_Object:
    return _dynamic_op(vm, OP.w_LE, w_a, w_b)

@OP.primitive('def(a: dynamic, b: dynamic) -> dynamic')
def dynamic_gt(vm: 'SPyVM', w_a: W_Object, w_b: W_Object) -> W_Object:
    return _dynamic_op(vm, OP.w_GT, w_a, w_b)

@OP.primitive('def(a: dynamic, b: dynamic) -> dynamic')
def dynamic_ge(vm: 'SPyVM', w_a: W_Object, w_b: W_Object) -> W_Object:
    return _dynamic_op(vm, OP.w_GE, w_a, w_b)
