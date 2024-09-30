from typing import TYPE_CHECKING
import fixedint
from spy.vm.w import W_I32
from . import UNSAFE
from .ptr import W_I32Ptr

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


# this is just a PoC, for now we hardcode i32 as the type.
@UNSAFE.builtin
def gc_alloc(vm: 'SPyVM', w_n: W_I32) -> W_I32Ptr:
    n = vm.unwrap_i32(w_n)
    size = 4 * n
    addr = vm.ll.call('spy_gc_alloc_mem', size)
    return W_I32Ptr(addr)
