from typing import TYPE_CHECKING, Annotated
import math
from spy.vm.primitive import W_F64, W_I32, W_Dynamic, W_Void
from spy.vm.b import B
from spy.vm.object import Member
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.builtin import builtin_func, builtin_type, builtin_method
from spy.vm.registry import ModuleRegistry

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

MATH = ModuleRegistry('math')

@MATH.builtin_func
def w_sqrt(vm: 'SPyVM', w_x: W_F64) -> W_F64:
    x = vm.unwrap_f64(w_x)
    res = math.sqrt(x)
    return vm.wrap(res)  # type: ignore
