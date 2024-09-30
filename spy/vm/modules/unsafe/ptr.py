from typing import TYPE_CHECKING
import fixedint
from spy.vm.b import B
from spy.vm.object import spytype
from spy.vm.w import W_Object, W_I32, W_Type, W_Void
from spy.vm.opimpl import W_OpImpl, W_Value
from . import UNSAFE
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@UNSAFE.spytype('i32ptr')
class W_I32Ptr(W_Object):
    # XXX: this works only if we target 32bit platforms such as wasm32, but we
    # need to think of a more general solution
    addr: fixedint.Int32

    def __init__(self, addr: int | fixedint.Int32) -> None:
        assert type(addr) in (int, fixedint.Int32)
        self.addr = fixedint.Int32(addr)

    def __repr__(self) -> str:
        return f'W_I32Ptr(0x{self.addr:x})'

    def spy_unwrap(self, vm: 'SPyVM') -> fixedint.Int32:
        return self.addr

    @staticmethod
    def op_GETITEM(vm: 'SPyVM', wv_ptr: W_Value, wv_i: W_Value) -> W_OpImpl:
        return W_OpImpl.simple(UNSAFE.w_i32ptr_get)

    @staticmethod
    def op_SETITEM(vm: 'SPyVM', wv_ptr: W_Value, wv_i: W_Value,
                   wv_v: W_Value) -> W_OpImpl:
        return W_OpImpl.simple(UNSAFE.w_i32ptr_set)


@UNSAFE.builtin
def i32ptr_set(vm: 'SPyVM', w_ptr: W_I32Ptr, w_i: W_I32,  w_v: W_I32) -> W_Void:
    base = w_ptr.addr
    i = vm.unwrap_i32(w_i)
    v = vm.unwrap_i32(w_v)
    # XXX we should introduce bound check
    addr = base + 4*i
    vm.ll.mem.write_i32(addr, v)

@UNSAFE.builtin
def i32ptr_get(vm: 'SPyVM', w_ptr: W_I32Ptr, w_i: W_I32) -> W_I32:
    base = w_ptr.addr
    i = vm.unwrap_i32(w_i)
    # XXX we should introduce bound check
    addr = base + 4*i
    return vm.wrap(vm.ll.mem.read_i32(addr))
