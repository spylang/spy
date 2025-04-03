from typing import TYPE_CHECKING, Any
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type
from spy.vm.primitive import W_I32, W_F64, W_Bool
from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

# the following style is a bit too verbose, but probably its not worth to
# overly coplicate things with metaprogramming.

def register_ops(T: str, WT: type[W_Object]):

    def _binop(vm: 'SPyVM', w_a: WT, w_b: WT, fn: Any) -> Any:
        a = w_a.value
        b = w_b.value
        res = fn(a, b)
        return vm.wrap(res)

    def _unary_op(vm: 'SPyVM', w_a: WT, fn: Any) -> Any:
        a = w_a.value
        res = fn(a)
        return WT(res)

    @OP.builtin_func(f'{T}_add')
    def w_add(vm: 'SPyVM', w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a + b)

    @OP.builtin_func(f'{T}_sub')
    def w_sub(vm: 'SPyVM', w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a - b)

    @OP.builtin_func(f'{T}_mul')
    def w_mul(vm: 'SPyVM', w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a * b)

    @OP.builtin_func(f'{T}_div')
    def w_div(vm: 'SPyVM', w_a: WT, w_b: WT) -> W_F64:
        return _binop(vm, w_a, w_b, lambda a, b: a / b)

    @OP.builtin_func(f'{T}_floordiv')
    def w_floordiv(vm: 'SPyVM', w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a // b)

    @OP.builtin_func(f'{T}_mod')
    def w_mod(vm: 'SPyVM', w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a % b)

    @OP.builtin_func(f'{T}_lshift')
    def w_lshift(vm: 'SPyVM', w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a << b)

    @OP.builtin_func(f'{T}_rshift')
    def w_rshift(vm: 'SPyVM', w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a >> b)

    @OP.builtin_func(f'{T}_and')
    def w_and(vm: 'SPyVM', w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a & b)

    @OP.builtin_func(f'{T}_or')
    def w_or(vm: 'SPyVM', w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a | b)

    @OP.builtin_func(f'{T}_xor')
    def w_xor(vm: 'SPyVM', w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a ^ b)

    @OP.builtin_func(f'{T}_eq')
    def w_eq(vm: 'SPyVM', w_a: WT, w_b: WT) -> W_Bool:
        return _binop(vm, w_a, w_b, lambda a, b: a == b)

    @OP.builtin_func(f'{T}_ne')
    def w_ne(vm: 'SPyVM', w_a: WT, w_b: WT) -> W_Bool:
        return _binop(vm, w_a, w_b, lambda a, b: a != b)

    @OP.builtin_func(f'{T}_lt')
    def w_lt(vm: 'SPyVM', w_a: WT, w_b: WT) -> W_Bool:
        return _binop(vm, w_a, w_b, lambda a, b: a < b)

    @OP.builtin_func(f'{T}_le')
    def w_le(vm: 'SPyVM', w_a: WT, w_b: WT) -> W_Bool:
        return _binop(vm, w_a, w_b, lambda a, b: a <= b)

    @OP.builtin_func(f'{T}_gt')
    def w_gt(vm: 'SPyVM', w_a: WT, w_b: WT) -> W_Bool:
        return _binop(vm, w_a, w_b, lambda a, b: a > b)

    @OP.builtin_func(f'{T}_ge')
    def w_ge(vm: 'SPyVM', w_a: WT, w_b: WT) -> W_Bool:
        return _binop(vm, w_a, w_b, lambda a, b: a >= b)

    @OP.builtin_func(f'{T}_neg')
    def w_neg(vm: 'SPyVM', w_a: WT) -> WT:
        return _unary_op(vm, w_a, lambda a: -a)


register_ops('i32', W_I32)
