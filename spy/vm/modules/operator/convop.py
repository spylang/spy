from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Type
from spy.vm.function import W_Func
from spy.vm.primitive import W_I32, W_F64, W_Bool
from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin_func
def w_i32_to_f64(vm: 'SPyVM', w_x: W_I32) -> W_F64:
    val = vm.unwrap_i32(w_x)
    return vm.wrap(float(val))

@OP.builtin_func
def w_i32_to_bool(vm: 'SPyVM', w_x: W_I32) -> W_Bool:
    val = vm.unwrap_i32(w_x)
    return vm.wrap(bool(val))
