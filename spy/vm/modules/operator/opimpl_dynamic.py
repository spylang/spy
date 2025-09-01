from typing import TYPE_CHECKING
from spy.vm.primitive import W_Dynamic
from spy.vm.str import W_Str
from spy.vm.function import W_Func
from spy.vm.opspec import W_MetaArg
from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

def _dynamic_op(vm: 'SPyVM', w_op: W_Func,
                w_a: W_Dynamic, w_b: W_Dynamic,
                ) -> W_Dynamic:
    wm_a = W_MetaArg.from_w_obj(vm, w_a)
    wm_b = W_MetaArg.from_w_obj(vm, w_b)
    w_opimpl = vm.call_OP(None, w_op, [wm_a, wm_b])
    return w_opimpl.execute(vm, [w_a, w_b])

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
def w_dynamic_setattr(vm: 'SPyVM', w_obj: W_Dynamic, w_name: W_Str,
                    w_value: W_Dynamic) -> W_Dynamic:
    wm_obj = W_MetaArg.from_w_obj(vm, w_obj)
    wm_name = W_MetaArg.from_w_obj(vm, w_name)
    wm_v = W_MetaArg.from_w_obj(vm, w_value)
    w_opimpl = vm.call_OP(None, OP.w_SETATTR, [wm_obj, wm_name, wm_v])
    return w_opimpl.execute(vm, [w_obj, w_name, w_value])

@OP.builtin_func
def w_dynamic_getattr(vm: 'SPyVM', w_obj: W_Dynamic,
                      w_name: W_Str) -> W_Dynamic:
    wm_obj = W_MetaArg.from_w_obj(vm, w_obj)
    wm_name = W_MetaArg.from_w_obj(vm, w_name)
    w_opimpl = vm.call_OP(None, OP.w_GETATTR, [wm_obj, wm_name])
    return w_opimpl.execute(vm, [w_obj, w_name])

@OP.builtin_func
def w_dynamic_call(vm: 'SPyVM', w_obj: W_Dynamic,
                   *args_w: W_Dynamic) -> W_Dynamic:
    all_args_w = [w_obj] + list(args_w)
    all_args_wm = [
        W_MetaArg.from_w_obj(vm, w_x)
        for i, w_x in enumerate(all_args_w)
    ]
    w_opimpl = vm.call_OP(None, OP.w_CALL, all_args_wm)
    return w_opimpl.execute(vm, all_args_w)
