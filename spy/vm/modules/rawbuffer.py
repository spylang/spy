"""
SPy `rawbuffer` module.
"""

from typing import TYPE_CHECKING
import struct
from spy.vm.primitive import W_F64, W_I32
from spy.vm.b import B
from spy.vm.w import W_Object
from spy.vm.registry import ModuleRegistry
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

RAW_BUFFER = RB = ModuleRegistry("rawbuffer")

@RB.builtin_type("RawBuffer")
class W_RawBuffer(W_Object):
    buf: bytearray

    def __init__(self, size: int) -> None:
        self.buf = bytearray(size)

    def spy_unwrap(self, vm: "SPyVM") -> bytearray:
        return self.buf


@RB.builtin_func
def w_rb_alloc(vm: "SPyVM", w_size: W_I32) -> W_RawBuffer:
    size = vm.unwrap_i32(w_size)
    return W_RawBuffer(size)

@RB.builtin_func
def w_rb_set_i32(vm: "SPyVM", w_rb: W_RawBuffer,
               w_offset: W_I32, w_val: W_I32) -> None:
    offset = vm.unwrap_i32(w_offset)
    val = vm.unwrap_i32(w_val)
    struct.pack_into("i", w_rb.buf, offset, val)

@RB.builtin_func
def w_rb_get_i32(vm: "SPyVM", w_rb: W_RawBuffer, w_offset: W_I32) -> W_I32:
    offset = vm.unwrap_i32(w_offset)
    val = struct.unpack_from("i", w_rb.buf, offset)[0]
    return vm.wrap(val)

@RB.builtin_func
def w_rb_set_f64(vm: "SPyVM", w_rb: W_RawBuffer,
               w_offset: W_I32, w_val: W_F64) -> None:
    offset = vm.unwrap_i32(w_offset)
    val = vm.unwrap_f64(w_val)
    struct.pack_into("d", w_rb.buf, offset, val)

@RB.builtin_func
def w_rb_get_f64(vm: "SPyVM", w_rb: W_RawBuffer, w_offset: W_I32) -> W_F64:
    offset = vm.unwrap_i32(w_offset)
    val = struct.unpack_from("d", w_rb.buf, offset)[0]
    return vm.wrap(val)
