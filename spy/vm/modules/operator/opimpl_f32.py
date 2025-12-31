from ctypes import c_float as float32
from typing import TYPE_CHECKING, Any

from spy.errors import SPyError
from spy.vm.object import W_Object
from spy.vm.primitive import W_F32, W_Bool

from . import OP

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


def _f32_op(vm: "SPyVM", w_a: W_Object, w_b: W_Object, fn: str) -> Any:
    a = vm.unwrap_f32(w_a)
    b = vm.unwrap_f32(w_b)
    res = vm.ll.call(f"spy_operator${fn}", a, b)
    return vm.wrap(float32(res))


def _f32_unary_op(vm: "SPyVM", w_a: W_Object, fn: Any) -> Any:
    a = vm.unwrap_f32(w_a)
    res = fn(a)
    return vm.wrap(res)


@OP.builtin_func
def w_f32_add(vm: "SPyVM", w_a: W_F32, w_b: W_F32) -> W_F32:
    return _f32_op(vm, w_a, w_b, "f32_add")
