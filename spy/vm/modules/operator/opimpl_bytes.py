from typing import TYPE_CHECKING

from spy.vm.bytes import W_Bytes
from spy.vm.primitive import W_I32, W_Bool

from . import OP

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin_func
def w_bytes_add(vm: "SPyVM", w_a: W_Bytes, w_b: W_Bytes) -> W_Bytes:
    assert isinstance(w_a, W_Bytes)
    assert isinstance(w_b, W_Bytes)
    ptr_c = vm.ll.call("spy_bytes_add", w_a.ptr, w_b.ptr)
    return W_Bytes.from_ptr(vm, ptr_c)


@OP.builtin_func
def w_bytes_mul(vm: "SPyVM", w_a: W_Bytes, w_b: W_I32) -> W_Bytes:
    assert isinstance(w_a, W_Bytes)
    assert isinstance(w_b, W_I32)
    ptr_c = vm.ll.call("spy_bytes_mul", w_a.ptr, w_b.value)
    return W_Bytes.from_ptr(vm, ptr_c)


@OP.builtin_func
def w_bytes_eq(vm: "SPyVM", w_a: W_Bytes, w_b: W_Bytes) -> W_Bool:
    assert isinstance(w_a, W_Bytes)
    assert isinstance(w_b, W_Bytes)
    res = vm.ll.call("spy_bytes_eq", w_a.ptr, w_b.ptr)
    return vm.wrap(bool(res))


@OP.builtin_func
def w_bytes_ne(vm: "SPyVM", w_a: W_Bytes, w_b: W_Bytes) -> W_Bool:
    assert isinstance(w_a, W_Bytes)
    assert isinstance(w_b, W_Bytes)
    res = vm.ll.call("spy_bytes_eq", w_a.ptr, w_b.ptr)
    return vm.wrap(bool(not res))
