"""
SPy `rawbuffer` module.
"""

from typing import TYPE_CHECKING
import struct
from spy.vm.b import B
from spy.vm.function import W_Func
from spy.vm.object import W_Type, W_Object, spytype, W_I32, W_F64, W_Void
from spy.vm.str import W_Str
from spy.vm.registry import ModuleRegistry
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

RAW_BUFFER = RB = ModuleRegistry('rawbuffer', '<rawbuffer>')

@spytype('RawBuffer')
class W_RawBuffer(W_Object):
    buf: bytearray

    def __init__(self, size: int) -> None:
        self.buf = bytearray(size)

    def spy_unwrap(self, vm: 'SPyVM') -> bytearray:
        return self.buf

RB.add('RawBuffer', W_RawBuffer._w)

@RB.primitive('def(size: i32) -> RawBuffer')
def rb_alloc(vm: 'SPyVM', w_size: W_I32) -> W_RawBuffer:
    size = vm.unwrap_i32(w_size)
    return W_RawBuffer(size)

@RB.primitive('def(rb: RawBuffer, offset: i32, val: i32) -> void')
def rb_set_i32(vm: 'SPyVM', w_rb: W_RawBuffer,
               w_offset: W_I32, w_val: W_I32) -> W_Void:
    offset = vm.unwrap_i32(w_offset)
    val = vm.unwrap_i32(w_val)
    struct.pack_into('i', w_rb.buf, offset, val)
    return B.w_None

@RB.primitive('def(rb: RawBuffer, offset: i32) -> i32')
def rb_get_i32(vm: 'SPyVM', w_rb: W_RawBuffer, w_offset: W_I32) -> W_I32:
    offset = vm.unwrap_i32(w_offset)
    val = struct.unpack_from('i', w_rb.buf, offset)[0]
    return vm.wrap(val)

@RB.primitive('def(rb: RawBuffer, offset: i32, val: f64) -> void')
def rb_set_f64(vm: 'SPyVM', w_rb: W_RawBuffer,
               w_offset: W_I32, w_val: W_F64) -> W_Void:
    offset = vm.unwrap_i32(w_offset)
    val = vm.unwrap_f64(w_val)
    struct.pack_into('d', w_rb.buf, offset, val)
    return B.w_None

@RB.primitive('def(rb: RawBuffer, offset: i32) -> f64')
def rb_get_f64(vm: 'SPyVM', w_rb: W_RawBuffer, w_offset: W_I32) -> W_F64:
    offset = vm.unwrap_i32(w_offset)
    val = struct.unpack_from('d', w_rb.buf, offset)[0]
    return vm.wrap(val)
