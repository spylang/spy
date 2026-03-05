from typing import TYPE_CHECKING

from spy.errors import SPyError
from spy.vm.primitive import W_I8, W_I32, W_U8, W_U32, W_Bool
from spy.vm.str import W_Str

from . import OP

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin_func
def w_str_add(vm: "SPyVM", w_a: W_Str, w_b: W_Str) -> W_Str:
    assert isinstance(w_a, W_Str)
    assert isinstance(w_b, W_Str)
    ptr_c = vm.ll.call("spy_str_add", w_a.ptr, w_b.ptr)
    return W_Str.from_ptr(vm, ptr_c)


@OP.builtin_func
def w_str_mul(vm: "SPyVM", w_a: W_Str, w_b: W_I32) -> W_Str:
    assert isinstance(w_a, W_Str)
    assert isinstance(w_b, W_I32)
    ptr_c = vm.ll.call("spy_str_mul", w_a.ptr, w_b.value)
    return W_Str.from_ptr(vm, ptr_c)


@OP.builtin_func
def w_str_eq(vm: "SPyVM", w_a: W_Str, w_b: W_Str) -> W_Bool:
    assert isinstance(w_a, W_Str)
    assert isinstance(w_b, W_Str)
    res = vm.ll.call("spy_str_eq", w_a.ptr, w_b.ptr)
    return vm.wrap(bool(res))


@OP.builtin_func
def w_str_ne(vm: "SPyVM", w_a: W_Str, w_b: W_Str) -> W_Bool:
    assert isinstance(w_a, W_Str)
    assert isinstance(w_b, W_Str)
    res = vm.ll.call("spy_str_eq", w_a.ptr, w_b.ptr)
    return vm.wrap(bool(not res))


def _parse_int(vm: "SPyVM", w_s: W_Str) -> int:
    s = vm.unwrap(w_s)
    try:
        return int(s)
    except ValueError:
        raise SPyError("W_ValueError", f"invalid literal for int() with base 10: {s!r}")


def _check_range(val: int, lo: int, hi: int, tname: str) -> None:
    if val < lo or val > hi:
        raise SPyError(
            "W_OverflowError", f"{tname} value {val} out of range [{lo}, {hi}]"
        )


@OP.builtin_func
def w_str_to_i32(vm: "SPyVM", w_s: W_Str) -> W_I32:
    val = _parse_int(vm, w_s)
    _check_range(val, -(2**31), 2**31 - 1, "i32")
    return W_I32(val)


@OP.builtin_func
def w_str_to_u32(vm: "SPyVM", w_s: W_Str) -> W_U32:
    val = _parse_int(vm, w_s)
    _check_range(val, 0, 2**32 - 1, "u32")
    return W_U32(val)


@OP.builtin_func
def w_str_to_i8(vm: "SPyVM", w_s: W_Str) -> W_I8:
    val = _parse_int(vm, w_s)
    _check_range(val, -128, 127, "i8")
    return W_I8(val)


@OP.builtin_func
def w_str_to_u8(vm: "SPyVM", w_s: W_Str) -> W_U8:
    val = _parse_int(vm, w_s)
    _check_range(val, 0, 255, "u8")
    return W_U8(val)
