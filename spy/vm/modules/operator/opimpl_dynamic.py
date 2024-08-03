from typing import TYPE_CHECKING, Any
from spy.errors import SPyTypeError
from spy.vm.b import B
from spy.vm.object import W_Dynamic, W_Type
from spy.vm.str import W_Str
from spy.vm.function import W_Func
from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

def _dynamic_op(vm: 'SPyVM', w_op: W_Func,
                w_a: W_Dynamic, w_b: W_Dynamic,
                ) -> W_Dynamic:
    w_ltype = vm.dynamic_type(w_a)
    w_rtype = vm.dynamic_type(w_b)
    w_opimpl = vm.call_function(w_op, [w_ltype, w_rtype])
    if w_opimpl is B.w_NotImplemented:
        token = OP.to_token(w_op)
        l = w_ltype.name
        r = w_rtype.name
        raise SPyTypeError(f'cannot do `{l}` {token} `{r}`')
    assert isinstance(w_opimpl, W_Func)
    return vm.call_function(w_opimpl, [w_a, w_b])


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
    w_otype = vm.dynamic_type(w_obj)
    w_vtype = vm.dynamic_type(w_value)
    w_opimpl = OP.w_SETATTR.pyfunc(vm, w_otype, w_attr, w_vtype)
    if w_opimpl is B.w_NotImplemented:
        o = w_otype.name
        v = w_vtype.name
        attr = vm.unwrap_str(w_attr)
        msg = f"type `{o}` does not support assignment to attribute '{attr}'"
        raise SPyTypeError(msg)
    return vm.call_function(w_opimpl, [w_obj, w_attr, w_value])
