from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.str import W_str
from spy.vm.object import W_i32
from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.primitive('def(a: str, b: str) -> str')
def str_add(vm: 'SPyVM', w_a: W_str, w_b: W_str) -> W_str:
    assert isinstance(w_a, W_str)
    assert isinstance(w_b, W_str)
    ptr_c = vm.ll.call('spy_str_add', w_a.ptr, w_b.ptr)
    return W_str.from_ptr(vm, ptr_c)

@OP.primitive('def(s: str, n: i32) -> str')
def str_mul(vm: 'SPyVM', w_a: W_str, w_b: W_i32) -> W_str:
    assert isinstance(w_a, W_str)
    assert isinstance(w_b, W_i32)
    ptr_c = vm.ll.call('spy_str_mul', w_a.ptr, w_b.value)
    return W_str.from_ptr(vm, ptr_c)

@OP.primitive('def(s: str, i: i32) -> str')
def str_getitem(vm: 'SPyVM', w_s: W_str, w_i: W_i32) -> W_str:
    assert isinstance(w_s, W_str)
    assert isinstance(w_i, W_i32)
    ptr_c = vm.ll.call('spy_str_getitem', w_s.ptr, w_i.value)
    return W_str.from_ptr(vm, ptr_c)
