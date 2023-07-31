from typing import TYPE_CHECKING, Any
from spy.vm.str import W_str
from spy.vm.object import W_Object
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

def str_add(vm: 'SPyVM', w_a: W_Object, w_b: W_Object) -> W_Object:
    assert isinstance(w_a, W_str)
    assert isinstance(w_b, W_str)
    ptr_c = vm.ll.call('spy_StrAdd', w_a.ptr, w_b.ptr)
    return W_str(vm, ptr_c)
