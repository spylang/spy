from ctypes import c_float as float32
from typing import TYPE_CHECKING, Any

from spy.vm.object import W_Object
from spy.vm.primitive import W_F32, W_Bool

from . import OP

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


def _f32_op_f32(vm: "SPyVM", w_a: W_Object, w_b: W_Object, fn: str) -> Any:
    a = vm.unwrap_f32(w_a)
    b = vm.unwrap_f32(w_b)
    res = vm.ll.call(f"spy_operator$f32_{fn}", a, b)
    return vm.wrap(float32(res))


def _f32_op_bool(vm: "SPyVM", w_a: W_Object, w_b: W_Object, fn: str) -> Any:
    a = vm.unwrap_f32(w_a)
    b = vm.unwrap_f32(w_b)
    res = vm.ll.call(f"spy_operator$f32_{fn}", a, b)
    return vm.wrap(bool(res))


@OP.builtin_func
def w_f32_add(vm: "SPyVM", w_a: W_F32, w_b: W_F32) -> W_F32:
    return _f32_op_f32(vm, w_a, w_b, "add")


@OP.builtin_func
def w_f32_sub(vm: "SPyVM", w_a: W_F32, w_b: W_F32) -> W_F32:
    return _f32_op_f32(vm, w_a, w_b, "sub")


@OP.builtin_func
def w_f32_mul(vm: "SPyVM", w_a: W_F32, w_b: W_F32) -> W_F32:
    return _f32_op_f32(vm, w_a, w_b, "mul")


@OP.builtin_func
def w_f32_div(vm: "SPyVM", w_a: W_F32, w_b: W_F32) -> W_F32:
    return _f32_op_f32(vm, w_a, w_b, "div")


@OP.builtin_func
def w_f32_floordiv(vm: "SPyVM", w_a: W_F32, w_b: W_F32) -> W_F32:
    return _f32_op_f32(vm, w_a, w_b, "floordiv")


@OP.builtin_func
def w_f32_mod(vm: "SPyVM", w_a: W_F32, w_b: W_F32) -> W_F32:
    return _f32_op_f32(vm, w_a, w_b, "mod")


@OP.builtin_func
def w_f32_eq(vm: "SPyVM", w_a: W_F32, w_b: W_F32) -> W_Bool:
    return _f32_op_bool(vm, w_a, w_b, "eq")


@OP.builtin_func
def w_f32_ne(vm: "SPyVM", w_a: W_F32, w_b: W_F32) -> W_Bool:
    return _f32_op_bool(vm, w_a, w_b, "ne")


@OP.builtin_func
def w_f32_lt(vm: "SPyVM", w_a: W_F32, w_b: W_F32) -> W_Bool:
    return _f32_op_bool(vm, w_a, w_b, "lt")


@OP.builtin_func
def w_f32_le(vm: "SPyVM", w_a: W_F32, w_b: W_F32) -> W_Bool:
    return _f32_op_bool(vm, w_a, w_b, "le")


@OP.builtin_func
def w_f32_gt(vm: "SPyVM", w_a: W_F32, w_b: W_F32) -> W_Bool:
    return _f32_op_bool(vm, w_a, w_b, "gt")


@OP.builtin_func
def w_f32_ge(vm: "SPyVM", w_a: W_F32, w_b: W_F32) -> W_Bool:
    return _f32_op_bool(vm, w_a, w_b, "ge")


@OP.builtin_func
def w_f32_neg(vm: "SPyVM", w_a: W_F32) -> W_F32:
    a = vm.unwrap_f32(w_a)
    res = vm.ll.call("spy_operator$f32_neg", a)
    return vm.wrap(float32(res))
