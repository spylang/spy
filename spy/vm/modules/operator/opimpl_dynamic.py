from typing import TYPE_CHECKING, Any
from spy.errors import SPyTypeError
from spy.vm.b import B
from spy.vm.object import W_Dynamic, W_Type
from spy.vm.str import W_Str
from spy.vm.function import W_Func
from spy.vm.opimpl import W_OpImpl, W_Value
from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

def _dynamic_op(vm: 'SPyVM', w_op: W_Func,
                w_a: W_Dynamic, w_b: W_Dynamic,
                ) -> W_Dynamic:
    from spy.vm.typechecker import typecheck_opimpl
    # this looks suspiciously like vm.eq & co., we should unify them
    token = OP.to_token(w_op)
    errmsg = 'cannot do `{0}` %s `{1}`' % token

    wv_a = W_Value.from_w_obj(vm, w_a, 'a', 0)
    wv_b = W_Value.from_w_obj(vm, w_b, 'b', 1)
    w_opimpl = vm.call_OP(w_op, [wv_a, wv_b])
    typecheck_opimpl(vm, w_opimpl, [wv_a, wv_b],
                     dispatch='multi',
                     errmsg=errmsg)
    return w_opimpl.call(vm, [w_a, w_b])

@OP.builtin
def dynamic_add(vm: 'SPyVM', w_a: W_Dynamic, w_b: W_Dynamic) -> W_Dynamic:
    return _dynamic_op(vm, OP.w_ADD, w_a, w_b)

@OP.builtin
def dynamic_mul(vm: 'SPyVM', w_a: W_Dynamic, w_b: W_Dynamic) -> W_Dynamic:
    return _dynamic_op(vm, OP.w_MUL, w_a, w_b)

@OP.builtin
def dynamic_eq(vm: 'SPyVM', w_a: W_Dynamic, w_b: W_Dynamic) -> W_Dynamic:
    # NOTE: == between dynamic uses UNIVERSAL_EQ
    return _dynamic_op(vm, OP.w_UNIVERSAL_EQ, w_a, w_b)

@OP.builtin
def dynamic_ne(vm: 'SPyVM', w_a: W_Dynamic, w_b: W_Dynamic) -> W_Dynamic:
    return _dynamic_op(vm, OP.w_UNIVERSAL_NE, w_a, w_b)

@OP.builtin
def dynamic_lt(vm: 'SPyVM', w_a: W_Dynamic, w_b: W_Dynamic) -> W_Dynamic:
    return _dynamic_op(vm, OP.w_LT, w_a, w_b)

@OP.builtin
def dynamic_le(vm: 'SPyVM', w_a: W_Dynamic, w_b: W_Dynamic) -> W_Dynamic:
    return _dynamic_op(vm, OP.w_LE, w_a, w_b)

@OP.builtin
def dynamic_gt(vm: 'SPyVM', w_a: W_Dynamic, w_b: W_Dynamic) -> W_Dynamic:
    return _dynamic_op(vm, OP.w_GT, w_a, w_b)

@OP.builtin
def dynamic_ge(vm: 'SPyVM', w_a: W_Dynamic, w_b: W_Dynamic) -> W_Dynamic:
    return _dynamic_op(vm, OP.w_GE, w_a, w_b)

@OP.builtin
def dynamic_setattr(vm: 'SPyVM', w_obj: W_Dynamic, w_attr: W_Str,
                    w_value: W_Dynamic) -> W_Dynamic:
    wv_obj = W_Value.from_w_obj(vm, w_obj, 'o', 0)
    wv_attr = W_Value.from_w_obj(vm, w_attr, 'a', 1)
    wv_v = W_Value.from_w_obj(vm, w_value, 'v', 2)
    w_opimpl = vm.call_OP(OP.w_SETATTR, [wv_obj, wv_attr, wv_v])
    return w_opimpl.call(vm, [w_obj, w_attr, w_value])
