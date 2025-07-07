from typing import TYPE_CHECKING
from spy.vm.primitive import W_Bool
from . import OP

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@OP.builtin_func('bool_eq')
def w_bool_eq(vm: 'SPyVM', w_a: W_Bool, w_b: W_Bool) -> W_Bool:
    return vm.wrap(w_a.value == w_b.value)  # type: ignore

@OP.builtin_func('bool_ne')
def w_bool_ne(vm: 'SPyVM', w_a: W_Bool, w_b: W_Bool) -> W_Bool:
    return vm.wrap(w_a.value != w_b.value)  # type: ignore