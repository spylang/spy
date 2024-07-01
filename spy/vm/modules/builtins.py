"""
Second half of the `builtins` module.

The first half is in vm/b.py. See its docstring for more details.
"""

from typing import TYPE_CHECKING, Any
from spy.vm.object import W_I32, W_F64, W_Bool, W_Dynamic, W_Void
from spy.vm.str import W_Str
from spy.vm.b import BUILTINS, B

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

PY_PRINT = print  # type: ignore

@BUILTINS.builtin
def abs(vm: 'SPyVM', w_x: W_I32) -> W_I32:
    x = vm.unwrap_i32(w_x)
    res = vm.ll.call('spy_builtins$abs', x)
    return vm.wrap(res) # type: ignore

@BUILTINS.builtin
def print(vm: 'SPyVM', w_x: W_Dynamic) -> W_Void:
    """
    Super minimal implementation of print().

    It takes just one argument.
    """
    if isinstance(w_x, (W_I32, W_F64, W_Bool, W_Str, W_Void)):
        PY_PRINT(vm.unwrap(w_x))
    else:
        PY_PRINT(w_x)
    return B.w_None


@BUILTINS.builtin
def print_i32(vm: 'SPyVM', w_x: W_I32) -> W_Void:
    PY_PRINT(vm.unwrap(w_x))

@BUILTINS.builtin
def print_f64(vm: 'SPyVM', w_x: W_F64) -> W_Void:
    PY_PRINT(vm.unwrap(w_x))

@BUILTINS.builtin
def print_bool(vm: 'SPyVM', w_x: W_Bool) -> W_Void:
    PY_PRINT(vm.unwrap(w_x))

@BUILTINS.builtin
def print_void(vm: 'SPyVM', w_x: W_Void) -> W_Void:
    PY_PRINT(vm.unwrap(w_x))

@BUILTINS.builtin
def print_str(vm: 'SPyVM', w_x: W_Str) -> W_Void:
    PY_PRINT(vm.unwrap(w_x))
