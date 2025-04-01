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

@MATH.builtin_func
def w_cos(vm: 'SPyVM', w_x: W_F64) -> W_F64:
    x = vm.unwrap_f64(w_x)
    res = math.cos(x)
    return vm.wrap(res)  # type: ignore

@MATH.builtin_func
def w_sin(vm: 'SPyVM', w_x: W_F64) -> W_F64:
    x = vm.unwrap_f64(w_x)
    res = math.sin(x)
    return vm.wrap(res)  # type: ignore

@MATH.builtin_func
def w_tan(vm: 'SPyVM', w_x: W_F64) -> W_F64:
    x = vm.unwrap_f64(w_x)
    res = math.tan(x)
    return vm.wrap(res)  # type: ignore

@MATH.builtin_func
def w_log(vm: 'SPyVM', w_x: W_F64) -> W_F64:
    x = vm.unwrap_f64(w_x)
    res = math.log(x)
    return vm.wrap(res)  # type: ignore

@MATH.builtin_func
def w_log10(vm: 'SPyVM', w_x: W_F64) -> W_F64:
    x = vm.unwrap_f64(w_x)
    res = math.log10(x)
    return vm.wrap(res)  # type: ignore

@MATH.builtin_func
def w_exp(vm: 'SPyVM', w_x: W_F64) -> W_F64:
    x = vm.unwrap_f64(w_x)
    res = math.exp(x)
    return vm.wrap(res)  # type: ignore

@MATH.builtin_func
def w_acos(vm: 'SPyVM', w_x: W_F64) -> W_F64:
    x = vm.unwrap_f64(w_x)
    res = math.acos(x)
    return vm.wrap(res)  # type: ignore

@MATH.builtin_func
def w_asin(vm: 'SPyVM', w_x: W_F64) -> W_F64:
    x = vm.unwrap_f64(w_x)
    res = math.asin(x)
    return vm.wrap(res)  # type: ignore

@MATH.builtin_func
def w_atan(vm: 'SPyVM', w_x: W_F64) -> W_F64:
    x = vm.unwrap_f64(w_x)
    res = math.atan(x)
    return vm.wrap(res)  # type: ignore

@MATH.builtin_func
def w_atan2(vm: 'SPyVM', w_y: W_F64, w_x: W_F64) -> W_F64:
    y = vm.unwrap_f64(w_y)
    x = vm.unwrap_f64(w_x)
    res = math.atan2(y, x)
    return vm.wrap(res)  # type: ignore

@MATH.builtin_func
def w_ceil(vm: 'SPyVM', w_x: W_F64) -> W_F64:
    x = vm.unwrap_f64(w_x)
    res = math.ceil(x)
    return vm.wrap(res)  # type: ignore

@MATH.builtin_func
def w_floor(vm: 'SPyVM', w_x: W_F64) -> W_F64:
    x = vm.unwrap_f64(w_x)
    res = math.floor(x)
    return vm.wrap(res)  # type: ignore

@MATH.builtin_func
def w_pow(vm: 'SPyVM', w_x: W_F64, w_y: W_F64) -> W_F64:
    x = vm.unwrap_f64(w_x)
    y = vm.unwrap_f64(w_y)
    res = math.pow(x, y)
    return vm.wrap(res)  # type: ignore

@MATH.builtin_func
def w_fabs(vm: 'SPyVM', w_x: W_F64) -> W_F64:
    x = vm.unwrap_f64(w_x)
    res = math.fabs(x)
    return vm.wrap(res)  # type: ignore
