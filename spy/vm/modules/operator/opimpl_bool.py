from typing import TYPE_CHECKING

from spy.vm.primitive import W_Bool

from . import OP

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin_func("bool_eq")
def w_bool_eq(vm: "SPyVM", w_a: W_Bool, w_b: W_Bool) -> W_Bool:
    return vm.wrap(w_a.value == w_b.value)


@OP.builtin_func("bool_ne")
def w_bool_ne(vm: "SPyVM", w_a: W_Bool, w_b: W_Bool) -> W_Bool:
    return vm.wrap(w_a.value != w_b.value)


@OP.builtin_func("bool_and")
def w_bool_and(vm: "SPyVM", w_a: W_Bool, w_b: W_Bool) -> W_Bool:
    return vm.wrap(w_a.value and w_b.value)


@OP.builtin_func("bool_or")
def w_bool_or(vm: "SPyVM", w_a: W_Bool, w_b: W_Bool) -> W_Bool:
    return vm.wrap(w_a.value or w_b.value)


@OP.builtin_func("bool_xor")
def w_bool_xor(vm: "SPyVM", w_a: W_Bool, w_b: W_Bool) -> W_Bool:
    return vm.wrap(w_a.value != w_b.value)


@OP.builtin_func("bool_lt")
def w_bool_lt(vm: "SPyVM", w_a: W_Bool, w_b: W_Bool) -> W_Bool:
    # False < True but not True < False
    return vm.wrap(not w_a.value and w_b.value)


@OP.builtin_func("bool_le")
def w_bool_le(vm: "SPyVM", w_a: W_Bool, w_b: W_Bool) -> W_Bool:
    # False <= True and True <= True and False <= False
    return vm.wrap(not w_a.value or w_b.value)


@OP.builtin_func("bool_gt")
def w_bool_gt(vm: "SPyVM", w_a: W_Bool, w_b: W_Bool) -> W_Bool:
    # True > False but not False > True
    return vm.wrap(w_a.value and not w_b.value)


@OP.builtin_func("bool_ge")
def w_bool_ge(vm: "SPyVM", w_a: W_Bool, w_b: W_Bool) -> W_Bool:
    # True >= False and True >= True and False >= False
    return vm.wrap(w_a.value or not w_b.value)

@OP.builtin_func('bool_not')
def w_bool_not(vm: 'SPyVM', w_a: W_Bool) -> W_Bool:
    return vm.wrap(not vm.unwrap_bool(w_a))
