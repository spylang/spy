from typing import TYPE_CHECKING, Annotated, Any, Protocol

from spy.errors import SPyError
from spy.location import Loc
from spy.vm.object import W_Object
from spy.vm.primitive import W_F64, W_I8, W_I32, W_U8, W_Bool

from . import OP

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

class W_IntLike(Protocol):
    "mypy protocol which works for W_I32, W_I8, etc."
    value: Any

def make_ops(T: str, pyclass: type[W_Object]) -> None:
    w_T = pyclass._w  # e.g. B.w_i32
    WT = Annotated[W_IntLike, w_T]

    def _binop(vm: "SPyVM", w_a: WT, w_b: WT, fn: Any) -> Any:
        a = w_a.value
        b = w_b.value
        res = fn(a, b)
        return vm.wrap(res)

    def _unary_op(vm: "SPyVM", w_a: WT, fn: Any) -> Any:
        a = w_a.value
        res = fn(a)
        return vm.wrap(res)

    # If T is 'i32', the following @OP.builtin_func define functions like these:
    #     builtins::i32_add
    #     builtins::i32_sub
    #     ...

    @OP.builtin_func(f"{T}_add")
    def w_add(vm: "SPyVM", w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a + b)

    @OP.builtin_func(f"{T}_sub")
    def w_sub(vm: "SPyVM", w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a - b)

    @OP.builtin_func(f"{T}_mul")
    def w_mul(vm: "SPyVM", w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a * b)

    @OP.builtin_func(f"{T}_div")
    def w_div(vm: "SPyVM", w_a: WT, w_b: WT) -> W_F64:
        if w_b.value == 0:
            raise SPyError("W_ZeroDivisionError", "division by zero")
        return _binop(vm, w_a, w_b, lambda a, b: a / b)

    @OP.builtin_func(f"{T}_floordiv")
    def w_floordiv(vm: "SPyVM", w_a: WT, w_b: WT) -> WT:
        if w_b.value == 0:
            raise SPyError("W_ZeroDivisionError", "integer division or modulo by zero")
        return _binop(vm, w_a, w_b, lambda a, b: a // b)

    @OP.builtin_func(f"{T}_mod")
    def w_mod(vm: "SPyVM", w_a: WT, w_b: WT) -> WT:
        if w_b.value == 0:
            raise SPyError("W_ZeroDivisionError", "integer modulo by zero")
        return _binop(vm, w_a, w_b, lambda a, b: a % b)

    @OP.builtin_func(f"{T}_lshift")
    def w_lshift(vm: "SPyVM", w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a << b)

    @OP.builtin_func(f"{T}_rshift")
    def w_rshift(vm: "SPyVM", w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a >> b)

    @OP.builtin_func(f"{T}_and")
    def w_and(vm: "SPyVM", w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a & b)

    @OP.builtin_func(f"{T}_or")
    def w_or(vm: "SPyVM", w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a | b)

    @OP.builtin_func(f"{T}_xor")
    def w_xor(vm: "SPyVM", w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a ^ b)

    @OP.builtin_func(f"{T}_eq")
    def w_eq(vm: "SPyVM", w_a: WT, w_b: WT) -> W_Bool:
        return _binop(vm, w_a, w_b, lambda a, b: a == b)

    @OP.builtin_func(f"{T}_ne")
    def w_ne(vm: "SPyVM", w_a: WT, w_b: WT) -> W_Bool:
        return _binop(vm, w_a, w_b, lambda a, b: a != b)

    @OP.builtin_func(f"{T}_lt")
    def w_lt(vm: "SPyVM", w_a: WT, w_b: WT) -> W_Bool:
        return _binop(vm, w_a, w_b, lambda a, b: a < b)

    @OP.builtin_func(f"{T}_le")
    def w_le(vm: "SPyVM", w_a: WT, w_b: WT) -> W_Bool:
        return _binop(vm, w_a, w_b, lambda a, b: a <= b)

    @OP.builtin_func(f"{T}_gt")
    def w_gt(vm: "SPyVM", w_a: WT, w_b: WT) -> W_Bool:
        return _binop(vm, w_a, w_b, lambda a, b: a > b)

    @OP.builtin_func(f"{T}_ge")
    def w_ge(vm: "SPyVM", w_a: WT, w_b: WT) -> W_Bool:
        return _binop(vm, w_a, w_b, lambda a, b: a >= b)

    @OP.builtin_func(f"{T}_neg")
    def w_neg(vm: "SPyVM", w_a: WT) -> WT:
        return _unary_op(vm, w_a, lambda a: -a)


make_ops("i32", W_I32)
make_ops("i8", W_I8)
make_ops("u8", W_U8)
