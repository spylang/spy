from typing import TYPE_CHECKING, Annotated, Any, Protocol

from spy.errors import SPyError
from spy.vm.b import B
from spy.vm.opspec import W_MetaArg
from spy.vm.primitive import (
    W_F64,
    W_I8,
    W_I32,
    W_U8,
)
from spy.vm.w import W_Object, W_OpSpec, W_Type

from . import UNSAFE

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@UNSAFE.builtin_func(color="blue", kind="metafunc")
def w_unchecked_div(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpSpec:
    w_T = meta_args_type(wam_l, wam_r)
    match w_T:
        case B.w_i8:
            return W_OpSpec(UNSAFE.w_i8_unchecked_div)
        case B.w_u8:
            return W_OpSpec(UNSAFE.w_u8_unchecked_div)
        case B.w_i32:
            return W_OpSpec(UNSAFE.w_i32_unchecked_div)
        case B.w_f64:
            return W_OpSpec(UNSAFE.w_f64_unchecked_div)
        case _:
            raise SPyError(
                "W_TypeError",
                f"Unsupported type `{w_T.fqn.human_name}` for unchecked division operation",
            )


@UNSAFE.builtin_func(color="blue", kind="metafunc")
def w_unchecked_floordiv(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpSpec:
    w_T = meta_args_type(wam_l, wam_r)
    match w_T:
        case B.w_i8:
            return W_OpSpec(UNSAFE.w_i8_unchecked_floordiv)
        case B.w_u8:
            return W_OpSpec(UNSAFE.w_u8_unchecked_floordiv)
        case B.w_i32:
            return W_OpSpec(UNSAFE.w_i32_unchecked_floordiv)
        case B.w_f64:
            return W_OpSpec(UNSAFE.w_f64_unchecked_floordiv)
        case _:
            raise SPyError(
                "W_TypeError",
                f"Unsupported type `{w_T.fqn.human_name}` for unchecked floordiv operation",
            )


@UNSAFE.builtin_func(color="blue", kind="metafunc")
def w_unchecked_mod(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpSpec:
    w_T = meta_args_type(wam_l, wam_r)
    match w_T:
        case B.w_i8:
            return W_OpSpec(UNSAFE.w_i8_unchecked_mod)
        case B.w_u8:
            return W_OpSpec(UNSAFE.w_u8_unchecked_mod)
        case B.w_i32:
            return W_OpSpec(UNSAFE.w_i32_unchecked_mod)
        case B.w_f64:
            return W_OpSpec(UNSAFE.w_f64_unchecked_mod)
        case _:
            raise SPyError(
                "W_TypeError",
                f"Unsupported type `{w_T.fqn.human_name}` for unchecked modulus operation",
            )


def meta_args_type(wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_Type:
    if (wam_l.w_static_T == B.w_f64) ^ (wam_r.w_static_T == B.w_f64):
        if wam_l.w_static_T != B.w_f64:
            return wam_r.w_static_T

    return wam_l.w_static_T


class W_NumLike(Protocol):
    "mypy protocol which works for W_I32, W_I8, etc."

    value: Any


def make_ops(T: str, pyclass: type[W_Object]) -> None:
    w_T = pyclass._w  # e.g. B.w_i32
    WT = Annotated[W_NumLike, w_T]

    def _binop(vm: "SPyVM", w_a: WT, w_b: WT, fn: Any) -> Any:
        a = w_a.value
        b = w_b.value
        res = fn(a, b)
        return vm.wrap(res)

    @UNSAFE.builtin_func(f"{T}_unchecked_div")
    def w_unchecked_div(vm: "SPyVM", w_a: WT, w_b: WT) -> W_F64:
        return _binop(vm, w_a, w_b, lambda a, b: a / b)

    @UNSAFE.builtin_func(f"{T}_unchecked_floordiv")
    def w_unchecked_floordiv(vm: "SPyVM", w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a // b)

    @UNSAFE.builtin_func(f"{T}_unchecked_mod")
    def w_unchecked_mod(vm: "SPyVM", w_a: WT, w_b: WT) -> WT:
        return _binop(vm, w_a, w_b, lambda a, b: a % b)


make_ops("i8", W_I8)
make_ops("u8", W_U8)
make_ops("i32", W_I32)
make_ops("f64", W_F64)
