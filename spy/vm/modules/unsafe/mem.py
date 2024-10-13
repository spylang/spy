from typing import TYPE_CHECKING
import fixedint
from spy.fqn import QN
from spy.vm.b import B
from spy.vm.w import W_I32, W_Func, W_Type, W_Dynamic
from spy.vm.sig import spy_builtin
from . import UNSAFE
from .ptr import W_Ptr, make_ptr_type

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@UNSAFE.builtin(color='blue')
def gc_alloc(vm: 'SPyVM', w_T: W_Type) -> W_Dynamic:
    t = w_T.name                                       # 'i32'
    w_ptr_type = make_ptr_type(vm, UNSAFE.w_ptr, w_T)  # ptr[i32]
    W_MyPtr = vm.unwrap(w_ptr_type)                    # W_Ptr[W_I32]

    assert w_T is B.w_i32
    ITEMSIZE = 4

    # XXX this is wrong, it will break as soon as we use two types with the
    # same SIZEOF
    @spy_builtin(QN(f'unsafe::gc_alloc/{ITEMSIZE}'))   # unsafe::gc_alloc/4
    def my_gc_alloc(vm: 'SPyVM', w_n: W_I32) -> W_MyPtr:
        n = vm.unwrap_i32(w_n)
        size = ITEMSIZE * n
        addr = vm.ll.call('spy_gc_alloc_mem', size)
        return W_MyPtr(addr)

    return vm.wrap(my_gc_alloc)
