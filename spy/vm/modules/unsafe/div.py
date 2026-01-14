from typing import TYPE_CHECKING, Annotated, Any, Protocol

from spy.errors import SPyError
from spy.vm.b import B
from spy.vm.modules.operator.multimethod import MultiMethodTable
from spy.vm.opspec import W_MetaArg
from spy.vm.primitive import W_F32, W_F64, W_I8, W_I32, W_U8, W_U32
from spy.vm.w import W_Object, W_OpSpec, W_Type

from . import UNSAFE

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@UNSAFE.builtin_func(color="blue", kind="metafunc")
def w_unchecked_div(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpSpec:
    if w_opspec := MM.get_binary_opspec("unchecked_div", wam_l, wam_r):
        return w_opspec
    else:
        l_type = wam_l.w_static_T.fqn.human_name
        r_type = wam_r.w_static_T.fqn.human_name

        raise SPyError(
            "W_TypeError",
            f"Unsupported types `{l_type}` / `{r_type}` for unchecked division operation",
        )


@UNSAFE.builtin_func(color="blue", kind="metafunc")
def w_unchecked_floordiv(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpSpec:
    if w_opspec := MM.get_binary_opspec("unchecked_floordiv", wam_l, wam_r):
        return w_opspec
    else:
        l_type = wam_l.w_static_T.fqn.human_name
        r_type = wam_r.w_static_T.fqn.human_name

        raise SPyError(
            "W_TypeError",
            f"Unsupported types `{l_type}` // `{r_type}` for unchecked floordiv operation",
        )


@UNSAFE.builtin_func(color="blue", kind="metafunc")
def w_unchecked_mod(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpSpec:
    if w_opspec := MM.get_binary_opspec("unchecked_mod", wam_l, wam_r):
        return w_opspec
    else:
        l_type = wam_l.w_static_T.fqn.human_name
        r_type = wam_r.w_static_T.fqn.human_name

        raise SPyError(
            "W_TypeError",
            f"Unsupported types `{l_type}` % `{r_type}` for unchecked modulus operation",
        )


@UNSAFE.builtin_func(color="blue", kind="metafunc")
def w_ieee754_div(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpSpec:
    if w_opspec := MM.get_binary_opspec("ieee754_div", wam_l, wam_r):
        return w_opspec
    else:
        l_type = wam_l.w_static_T.fqn.human_name
        r_type = wam_r.w_static_T.fqn.human_name

        raise SPyError(
            "W_TypeError",
            f"Unsupported types `{l_type}` / `{r_type}` for unchecked ieee754 division operation",
        )


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
        if w_b.value == 0:
            raise SPyError("W_PanicError", "division by zero")
        return _binop(vm, w_a, w_b, lambda a, b: a / b)

    @UNSAFE.builtin_func(f"{T}_unchecked_floordiv")
    def w_unchecked_floordiv(vm: "SPyVM", w_a: WT, w_b: WT) -> WT:
        if w_b.value == 0:
            raise SPyError("W_PanicError", "integer division or modulo by zero")
        return _binop(vm, w_a, w_b, lambda a, b: a // b)

    @UNSAFE.builtin_func(f"{T}_unchecked_mod")
    def w_unchecked_mod(vm: "SPyVM", w_a: WT, w_b: WT) -> WT:
        if w_b.value == 0:
            raise SPyError("W_PanicError", "integer modulo by zero")
        return _binop(vm, w_a, w_b, lambda a, b: a % b)


make_ops("i8", W_I8)
make_ops("u8", W_U8)
make_ops("i32", W_I32)
make_ops("u32", W_U32)


@UNSAFE.builtin_func
def w_f64_unchecked_div(vm: "SPyVM", w_a: W_F64, w_b: W_F64) -> W_F64:
    if w_b.value == 0:
        raise SPyError("W_PanicError", "float division by zero")
    a = w_a.value
    b = w_b.value
    return vm.wrap(a / b)


@UNSAFE.builtin_func
def w_f64_unchecked_floordiv(vm: "SPyVM", w_a: W_F64, w_b: W_F64) -> W_F64:
    if w_b.value == 0:
        raise SPyError("W_PanicError", "float floor division by zero")
    a = w_a.value
    b = w_b.value
    return vm.wrap(a // b)


@UNSAFE.builtin_func
def w_f64_unchecked_mod(vm: "SPyVM", w_a: W_F64, w_b: W_F64) -> W_F64:
    if w_b.value == 0:
        raise SPyError("W_PanicError", "float modulo by zero")
    a = w_a.value
    b = w_b.value
    return vm.wrap(a % b)


@UNSAFE.builtin_func
def w_f32_unchecked_div(vm: "SPyVM", w_a: W_F32, w_b: W_F32) -> W_F32:
    a = vm.unwrap_f32(w_a)
    b = vm.unwrap_f32(w_b)
    res = vm.ll.call("spy_unsafe$f32_unchecked_div", a, b)
    return vm.wrap(res)


@UNSAFE.builtin_func
def w_f32_unchecked_floordiv(vm: "SPyVM", w_a: W_F32, w_b: W_F32) -> W_F32:
    a = vm.unwrap_f32(w_a)
    b = vm.unwrap_f32(w_b)
    res = vm.ll.call("spy_unsafe$f32_unchecked_floordiv", a, b)
    return vm.wrap(res)


@UNSAFE.builtin_func
def w_f32_unchecked_mod(vm: "SPyVM", w_a: W_F32, w_b: W_F32) -> W_F32:
    a = vm.unwrap_f32(w_a)
    b = vm.unwrap_f32(w_b)
    res = vm.ll.call("spy_unsafe$f32_unchecked_mod", a, b)
    return vm.wrap(res)


@UNSAFE.builtin_func
def w_f64_ieee754_div(vm: "SPyVM", w_a: W_F64, w_b: W_F64) -> W_F64:
    a = w_a.value
    b = w_b.value

    if b == 0:
        if a > 0:
            result = float("inf")
        elif a < 0:
            result = float("-inf")
        else:
            result = float("nan")

        return vm.wrap(result)

    return vm.wrap(a / b)


@UNSAFE.builtin_func
def w_f32_ieee754_div(vm: "SPyVM", w_a: W_F32, w_b: W_F32) -> W_F32:
    a = vm.unwrap_f32(w_a)
    b = vm.unwrap_f32(w_b)
    res = vm.ll.call("spy_unsafe$f32_ieee754_div", a, b)
    return vm.wrap(res)


MM = MultiMethodTable()

MM.register("unchecked_div", "i8", "i8", UNSAFE.w_i8_unchecked_div)
MM.register("unchecked_div", "u8", "u8", UNSAFE.w_u8_unchecked_div)
MM.register("unchecked_div", "i32", "i32", UNSAFE.w_i32_unchecked_div)
MM.register("unchecked_div", "u32", "u32", UNSAFE.w_u32_unchecked_div)
MM.register("unchecked_div", "f64", "f64", UNSAFE.w_f64_unchecked_div)
MM.register("unchecked_div", "f32", "f32", UNSAFE.w_f32_unchecked_div)
MM.register("unchecked_floordiv", "i8", "i8", UNSAFE.w_i8_unchecked_floordiv)
MM.register("unchecked_floordiv", "u8", "u8", UNSAFE.w_u8_unchecked_floordiv)
MM.register("unchecked_floordiv", "i32", "i32", UNSAFE.w_i32_unchecked_floordiv)
MM.register("unchecked_floordiv", "u32", "u32", UNSAFE.w_u32_unchecked_floordiv)
MM.register("unchecked_floordiv", "f64", "f64", UNSAFE.w_f64_unchecked_floordiv)
MM.register("unchecked_floordiv", "f32", "f32", UNSAFE.w_f32_unchecked_floordiv)
MM.register("unchecked_mod", "i8", "i8", UNSAFE.w_i8_unchecked_mod)
MM.register("unchecked_mod", "u8", "u8", UNSAFE.w_u8_unchecked_mod)
MM.register("unchecked_mod", "i32", "i32", UNSAFE.w_i32_unchecked_mod)
MM.register("unchecked_mod", "u32", "u32", UNSAFE.w_u32_unchecked_mod)
MM.register("unchecked_mod", "f64", "f64", UNSAFE.w_f64_unchecked_mod)
MM.register("unchecked_mod", "f32", "f32", UNSAFE.w_f32_unchecked_mod)

# float op combinations
for num_t in ["i8", "u8", "i32", "f32"]:
    MM.register("unchecked_div", "f64", num_t, UNSAFE.w_f64_unchecked_div)
    MM.register("unchecked_div", num_t, "f64", UNSAFE.w_f64_unchecked_div)
    MM.register("unchecked_floordiv", "f64", num_t, UNSAFE.w_f64_unchecked_floordiv)
    MM.register("unchecked_floordiv", num_t, "f64", UNSAFE.w_f64_unchecked_floordiv)
    MM.register("unchecked_mod", "f64", num_t, UNSAFE.w_f64_unchecked_mod)
    MM.register("unchecked_mod", num_t, "f64", UNSAFE.w_f64_unchecked_mod)

for int_t in ["i32"]:
    MM.register("unchecked_div", "f32", int_t, UNSAFE.w_f32_unchecked_div)
    MM.register("unchecked_div", int_t, "f32", UNSAFE.w_f32_unchecked_div)
    MM.register("unchecked_floordiv", "f32", int_t, UNSAFE.w_f32_unchecked_floordiv)
    MM.register("unchecked_floordiv", int_t, "f32", UNSAFE.w_f32_unchecked_floordiv)
    MM.register("unchecked_mod", "f32", int_t, UNSAFE.w_f32_unchecked_mod)
    MM.register("unchecked_mod", int_t, "f32", UNSAFE.w_f32_unchecked_mod)


# ieee754_div ops
MM.register("ieee754_div", "f64", "f64", UNSAFE.w_f64_ieee754_div)
MM.register("ieee754_div", "i32", "i32", UNSAFE.w_f64_ieee754_div)
MM.register("ieee754_div", "i32", "f64", UNSAFE.w_f64_ieee754_div)
MM.register("ieee754_div", "f64", "i32", UNSAFE.w_f64_ieee754_div)
MM.register("ieee754_div", "f32", "f64", UNSAFE.w_f64_ieee754_div)
MM.register("ieee754_div", "f64", "f32", UNSAFE.w_f64_ieee754_div)
MM.register("ieee754_div", "f32", "f32", UNSAFE.w_f32_ieee754_div)
MM.register("ieee754_div", "f32", "i32", UNSAFE.w_f32_ieee754_div)
MM.register("ieee754_div", "i32", "f32", UNSAFE.w_f32_ieee754_div)
