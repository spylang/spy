from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.str import W_Str
from spy.vm.object import W_I32, W_Bool
from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin
def str_add(vm: 'SPyVM', w_a: W_Str, w_b: W_Str) -> W_Str:
    assert isinstance(w_a, W_Str)
    assert isinstance(w_b, W_Str)
    ptr_c = vm.ll.call('spy_str_add', w_a.ptr, w_b.ptr)
    return W_Str.from_ptr(vm, ptr_c)

@OP.builtin
def str_mul(vm: 'SPyVM', w_a: W_Str, w_b: W_I32) -> W_Str:
    assert isinstance(w_a, W_Str)
    assert isinstance(w_b, W_I32)
    ptr_c = vm.ll.call('spy_str_mul', w_a.ptr, w_b.value)
    return W_Str.from_ptr(vm, ptr_c)

@OP.builtin
def str_eq(vm: 'SPyVM', w_a: W_Str, w_b: W_Str) -> W_Bool:
    assert isinstance(w_a, W_Str)
    assert isinstance(w_b, W_Str)
    res = vm.ll.call('spy_str_eq', w_a.ptr, w_b.ptr)
    return vm.wrap(bool(res))  # type: ignore

@OP.builtin
def str_ne(vm: 'SPyVM', w_a: W_Str, w_b: W_Str) -> W_Bool:
    assert isinstance(w_a, W_Str)
    assert isinstance(w_b, W_Str)
    res = vm.ll.call('spy_str_eq', w_a.ptr, w_b.ptr)
    return vm.wrap(bool(not res))  # type: ignore
