from typing import TYPE_CHECKING, Any

from spy.errors import SPyError
from spy.vm.object import W_Object
from spy.vm.primitive import W_Bool, W_Complex128

from . import OP

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


def _complex128_op(vm: "SPyVM", w_a: W_Object, w_b: W_Object, fn: Any) -> Any:
    a = vm.unwrap_complex128(w_a)
    b = vm.unwrap_complex128(w_b)
    res = fn(a, b)
    return vm.wrap(res)


def _complex128_unary_op(vm: "SPyVM", w_a: W_Object, fn: Any) -> Any:
    a = vm.unwrap_complex128(w_a)
    res = fn(a)
    return vm.wrap(res)


@OP.builtin_func
def w_complex128_add(vm: "SPyVM", w_a: W_Complex128, w_b: W_Complex128) -> W_Complex128:
    return _complex128_op(vm, w_a, w_b, lambda a, b: a + b)


@OP.builtin_func
def w_complex128_sub(vm: "SPyVM", w_a: W_Complex128, w_b: W_Complex128) -> W_Complex128:
    return _complex128_op(vm, w_a, w_b, lambda a, b: a - b)


@OP.builtin_func
def w_complex128_mul(vm: "SPyVM", w_a: W_Complex128, w_b: W_Complex128) -> W_Complex128:
    return _complex128_op(vm, w_a, w_b, lambda a, b: a * b)


@OP.builtin_func
def w_complex128_div(vm: "SPyVM", w_a: W_Complex128, w_b: W_Complex128) -> W_Complex128:
    if w_b.value == 0j:
        raise SPyError("W_ZeroDivisionError", "complex division by zero")
    return _complex128_op(vm, w_a, w_b, lambda a, b: a / b)


@OP.builtin_func
def w_complex128_eq(vm: "SPyVM", w_a: W_Complex128, w_b: W_Complex128) -> W_Bool:
    return _complex128_op(vm, w_a, w_b, lambda a, b: a == b)


@OP.builtin_func
def w_complex128_ne(vm: "SPyVM", w_a: W_Complex128, w_b: W_Complex128) -> W_Bool:
    return _complex128_op(vm, w_a, w_b, lambda a, b: a != b)


@OP.builtin_func
def w_complex128_neg(vm: "SPyVM", w_a: W_Complex128) -> W_Complex128:
    return _complex128_unary_op(vm, w_a, lambda a: -a)
