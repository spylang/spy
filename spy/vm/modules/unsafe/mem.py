from typing import TYPE_CHECKING, no_type_check
import fixedint
from spy.fqn import QN
from spy.vm.b import B
from spy.vm.w import W_I32, W_Func, W_Type, W_Dynamic, W_Object
from spy.vm.builtin import builtin_func
from . import UNSAFE
from .ptr import W_Ptr, make_ptr_type, hack_hack_fix_typename
from .misc import sizeof

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@UNSAFE.builtin_func(color='blue')
def gc_alloc(vm: 'SPyVM', w_T: W_Type) -> W_Dynamic:
    t = w_T.name                         # 'i32'
    w_ptr_type = vm.call(make_ptr_type, [w_T])  # ptr[i32]
    W_MyPtr = vm.unwrap(w_ptr_type)      # W_Ptr[W_I32]
    ITEMSIZE = sizeof(w_T)

    # this is a special builtin function, its C equivalent is automatically
    # generated by c.Context.new_ptr_type
    @no_type_check
    @builtin_func(QN(f'unsafe::ptr_{t}_gc_alloc'))   # unsafe::ptr_i32_gc_alloc
    def my_gc_alloc(vm: 'SPyVM', w_n: W_I32) -> W_MyPtr:
        n = vm.unwrap_i32(w_n)
        size = ITEMSIZE * n
        addr = vm.ll.call('spy_gc_alloc_mem', size)
        return W_MyPtr(addr, n)

    return vm.wrap(my_gc_alloc)


@UNSAFE.builtin_func(color='blue')
def mem_read(vm: 'SPyVM', w_T: W_Type) -> W_Dynamic:
    T = w_T.pyclass
    t = w_T.name
    t = hack_hack_fix_typename(t)

    @no_type_check
    @builtin_func(QN(f'unsafe::mem_read_{t}'))
    def mem_read_T(vm: 'SPyVM', w_addr: W_I32) -> T:
        addr = vm.unwrap_i32(w_addr)
        if w_T is B.w_i32:
            return vm.wrap(vm.ll.mem.read_i32(addr))
        elif w_T is B.w_f64:
            return vm.wrap(vm.ll.mem.read_f64(addr))
        elif issubclass(w_T.pyclass, W_Ptr):
            return w_T.pyclass(addr, 1)
        else:
            assert False

    return vm.wrap(mem_read_T)


@UNSAFE.builtin_func(color='blue')
def mem_write(vm: 'SPyVM', w_T: W_Type) -> W_Dynamic:
    T = w_T.pyclass
    t = w_T.name

    @no_type_check
    @builtin_func(QN(f'unsafe::mem_write_{t}'))
    def mem_write_T(vm: 'SPyVM', w_addr: W_I32, w_val: T) -> None:
        addr = vm.unwrap_i32(w_addr)
        if w_T is B.w_i32:
            v = vm.unwrap_i32(w_val)
            vm.ll.mem.write_i32(addr, v)
        elif w_T is B.w_f64:
            v = vm.unwrap_f64(w_val)
            vm.ll.mem.write_f64(addr, v)
        else:
            assert False

    return vm.wrap(mem_write_T)
