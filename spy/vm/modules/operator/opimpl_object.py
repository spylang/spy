from typing import TYPE_CHECKING, Any
from spy.vm.b import B
from spy.vm.object import W_Object, W_Bool
from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin
def object_is(vm: 'SPyVM', w_a: W_Object, w_b: W_Object) -> W_Bool:
    return vm.wrap(w_a is w_b)  # type: ignore

@OP.builtin
def object_isnot(vm: 'SPyVM', w_a: W_Object, w_b: W_Object) -> W_Bool:
    return vm.wrap(w_a is not w_b)  # type: ignore

@OP.builtin
def object_universal_eq(vm: 'SPyVM', w_a: W_Object, w_b: W_Object) -> W_Bool:
    return vm.universal_eq(w_a, w_b)

@OP.builtin
def object_universal_ne(vm: 'SPyVM', w_a: W_Object, w_b: W_Object) -> W_Bool:
    return vm.universal_ne(w_a, w_b)
