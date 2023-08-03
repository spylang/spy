from typing import TYPE_CHECKING, Any
from spy.vm.str import W_str
from spy.vm.object import W_Object, W_i32
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

def get(funcname: str) -> Any:
    func = globals().get(funcname)
    if func is None:
        raise KeyError(f'Cannot find {funcname} in helpers.py')
    return func

def StrAdd(vm: 'SPyVM', w_a: W_Object, w_b: W_Object) -> W_str:
    assert isinstance(w_a, W_str)
    assert isinstance(w_b, W_str)
    ptr_c = vm.ll.call('spy_StrAdd', w_a.ptr, w_b.ptr)
    return W_str.from_ptr(vm, ptr_c)

def StrMul(vm: 'SPyVM', w_a: W_Object, w_b: W_Object) -> W_str:
    assert isinstance(w_a, W_str)
    assert isinstance(w_b, W_i32)
    ptr_c = vm.ll.call('spy_StrMul', w_a.ptr, w_b.value)
    return W_str.from_ptr(vm, ptr_c)

def StrGetItem(vm: 'SPyVM', w_s: W_Object, w_i: W_Object) -> W_str:
    assert isinstance(w_s, W_str)
    assert isinstance(w_i, W_i32)
    ptr_c = vm.ll.call('spy_StrGetItem', w_s.ptr, w_i.value)
    return W_str.from_ptr(vm, ptr_c)
