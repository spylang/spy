from ctypes import c_float as float32
from typing import TYPE_CHECKING, Any

from spy.errors import SPyError
from spy.vm.object import W_Object
from spy.vm.primitive import W_F32, W_Bool

from . import OP

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin_func
def w_f32_add(vm: "SPyVM", w_a: W_F32, w_b: W_F32) -> W_F32:
    a = vm.unwrap_f32(w_a)
    b = vm.unwrap_f32(w_b)
    res = a.value + b.value
    return vm.wrap(float32(res))
