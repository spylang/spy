from typing import TYPE_CHECKING, Any
from spy.errors import SPyTypeError
from spy.vm.b import B
from spy.vm.object import W_Dynamic, W_Type
from spy.vm.str import W_Str
from spy.vm.function import W_Func
from spy.vm.opimpl import W_OpImpl, W_OpArg
from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

def _dynamic_op(vm: 'SPyVM', w_op: W_Func,
                w_a: W_Dynamic, w_b: W_Dynamic,
                ) -> W_Dynamic:
    wop_a = W_OpArg.from_w_obj(vm, w_a, 'a', 0)
    wop_b = W_OpArg.from_w_obj(vm, w_b, 'b', 1)
    w_opimpl = vm.call_OP(w_op, [wop_a, wop_b])
    return w_opimpl.call(vm, [w_a, w_b])

@OP.builtin_func
def w_dynamic_add(vm: 'SPyVM', w_a: W_Dynamic, w_b: W_Dynamic) -> W_Dynamic:
    return _dynamic_op(vm, OP.w_ADD, w_a, w_b)

@OP.builtin_func
def w_dynamic_mul(vm: 'SPyVM', w_a: W_Dynamic, w_b: W_Dynamic) -> W_Dynamic:
    return _dynamic_op(vm, OP.w_MUL, w_a, w_b)

@OP.builtin_func
def w_dynamic_eq(vm: 'SPyVM', w_a: W_Dynamic, w_b: W_Dynamic) -> W_Dynamic:
    # NOTE: == between dynamic uses UNIVERSAL_EQ
    return _dynamic_op(vm, OP.w_UNIVERSAL_EQ, w_a, w_b)

@OP.builtin_func
def w_dynamic_ne(vm: 'SPyVM', w_a: W_Dynamic, w_b: W_Dynamic) -> W_Dynamic:
    return _dynamic_op(vm, OP.w_UNIVERSAL_NE, w_a, w_b)

@OP.builtin_func
def w_dynamic_lt(vm: 'SPyVM', w_a: W_Dynamic, w_b: W_Dynamic) -> W_Dynamic:
    return _dynamic_op(vm, OP.w_LT, w_a, w_b)

@OP.builtin_func
def w_dynamic_le(vm: 'SPyVM', w_a: W_Dynamic, w_b: W_Dynamic) -> W_Dynamic:
    return _dynamic_op(vm, OP.w_LE, w_a, w_b)

@OP.builtin_func
def w_dynamic_gt(vm: 'SPyVM', w_a: W_Dynamic, w_b: W_Dynamic) -> W_Dynamic:
    return _dynamic_op(vm, OP.w_GT, w_a, w_b)

@OP.builtin_func
def w_dynamic_ge(vm: 'SPyVM', w_a: W_Dynamic, w_b: W_Dynamic) -> W_Dynamic:
    return _dynamic_op(vm, OP.w_GE, w_a, w_b)

@OP.builtin_func
def w_dynamic_setattr(vm: 'SPyVM', w_obj: W_Dynamic, w_attr: W_Str,
                    w_value: W_Dynamic) -> W_Dynamic:
    wop_obj = W_OpArg.from_w_obj(vm, w_obj, 'o', 0)
    wop_attr = W_OpArg.from_w_obj(vm, w_attr, 'a', 1)
    wop_v = W_OpArg.from_w_obj(vm, w_value, 'v', 2)
    w_opimpl = vm.call_OP(OP.w_SETATTR, [wop_obj, wop_attr, wop_v])
    return w_opimpl.call(vm, [w_obj, w_attr, w_value])
