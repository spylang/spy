import math
from typing import TYPE_CHECKING, Annotated, Optional

from spy.errors import SPyError
from spy.vm.b import B
from spy.vm.function import W_Func
from spy.vm.modules.operator import OP
from spy.vm.object import W_Object, W_Type
from spy.vm.opimpl import W_OpImpl
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_F64, W_I8, W_I32, W_U8, W_U32, W_Bool, W_Dynamic

from . import OP
from .multimethod import MultiMethodTable

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

MM = MultiMethodTable()


@OP.builtin_func(color="blue")
def w_CONVERT(
    vm: "SPyVM", wam_expT: W_MetaArg, wam_gotT: W_MetaArg, wam_x: W_MetaArg
) -> W_OpImpl:
    """
    Return a w_func which can convert the given MetaArg to the desired type.

    If the types are not compatible, raise SPyError. In this case,
    the caller can catch the error, add extra info and re-raise.
    """
    from spy.vm.typechecker import typecheck_opspec

    w_opspec = get_opspec(vm, wam_expT, wam_gotT, wam_x)
    if w_opspec.is_simple():
        # this is a bit of a hack, but I think it improves usability. By default, simple
        # opspec are called with ALL their arguments, including wam_exp. But for the
        # specific case of __convert_*__, we almast always want to call it with only the
        # actual to-be-converted argument, so here we change "the default".
        w_opspec = W_OpSpec(w_opspec._w_func, [wam_x])

    return typecheck_opspec(
        vm,
        w_opspec,
        [wam_expT, wam_gotT, wam_x],
        dispatch="convert",
        errmsg="mismatched types",
    )


def get_opspec(
    vm: "SPyVM", wam_expT: W_MetaArg, wam_gotT: W_MetaArg, wam_x: W_MetaArg
) -> W_OpSpec:
    w_expT = wam_expT.blue_ensure(vm, B.w_type)
    w_gotT = wam_gotT.blue_ensure(vm, B.w_type)
    assert isinstance(w_expT, W_Type)
    assert isinstance(w_gotT, W_Type)

    # this condition is checked by CONVERT_maybe. If we want this function to
    # become more generally usable, we might want to return an identity func
    # here.
    assert not vm.issubclass(w_gotT, w_expT)

    if vm.issubclass(w_expT, w_gotT):
        # this handles two separate cases:
        #   - upcasts, e.g. object->i32: in this case we just do a typecheck
        #   - dynamic->*: in this case we SHOULD do actual conversions, but at
        #                 the moment we don't so we conflate the two cases
        #                 into one
        w_from_dynamic_T = vm.fast_call(OP.w_from_dynamic, [w_expT])
        assert isinstance(w_from_dynamic_T, W_Func)
        return W_OpSpec(w_from_dynamic_T)

    w_opspec = MM.lookup("convert", w_gotT, w_expT)
    if w_opspec is not None:
        return w_opspec

    elif w_conv_to := w_gotT.lookup_func("__convert_to__"):
        w_opspec = vm.fast_metacall(w_conv_to, [wam_expT, wam_gotT, wam_x])
        return w_opspec

    elif w_conv_from := w_expT.lookup_func("__convert_from__"):
        w_opspec = vm.fast_metacall(w_conv_from, [wam_expT, wam_gotT, wam_x])
        return w_opspec

    return W_OpSpec.NULL


def CONVERT_maybe(
    vm: "SPyVM",
    wam_expT: W_MetaArg,
    wam_x: W_MetaArg,
) -> Optional[W_OpImpl]:
    """
    Same as w_CONVERT, but return None if the types are already compatible.
    """
    assert wam_expT.color == "blue"
    w_expT = wam_expT.w_blueval
    assert isinstance(w_expT, W_Type)
    w_gotT = wam_x.w_static_T
    if vm.issubclass(w_gotT, w_expT):
        # nothing to do
        return None
    wam_gotT = W_MetaArg.from_w_obj(vm, w_gotT, loc=wam_x.loc)
    return vm.fast_call(OP.w_CONVERT, [wam_expT, wam_gotT, wam_x])  # type: ignore


@OP.builtin_func
def w_i32_to_f64(vm: "SPyVM", w_x: W_I32) -> W_F64:
    val = vm.unwrap_i32(w_x)
    return vm.wrap(float(val))


@OP.builtin_func
def w_u32_to_f64(vm: "SPyVM", w_x: W_U32) -> W_F64:
    val = vm.unwrap_u32(w_x)
    return vm.wrap(float(val))


@OP.builtin_func
def w_i8_to_f64(vm: "SPyVM", w_x: W_I8) -> W_F64:
    val = vm.unwrap_i8(w_x)
    return vm.wrap(float(val))


@OP.builtin_func
def w_u8_to_f64(vm: "SPyVM", w_x: W_U8) -> W_F64:
    val = vm.unwrap_u8(w_x)
    return vm.wrap(float(val))


@OP.builtin_func
def w_i32_to_bool(vm: "SPyVM", w_x: W_I32) -> W_Bool:
    val = vm.unwrap_i32(w_x)
    return vm.wrap(bool(val))


@OP.builtin_func
def w_i32_to_i8(vm: "SPyVM", w_x: W_I32) -> W_I8:
    return W_I8(w_x.value)


@OP.builtin_func
def w_i8_to_i32(vm: "SPyVM", w_x: W_I8) -> W_I32:
    return W_I32(w_x.value)


@OP.builtin_func
def w_i32_to_u8(vm: "SPyVM", w_x: W_I32) -> W_U8:
    return W_U8(w_x.value)


@OP.builtin_func
def w_u8_to_i32(vm: "SPyVM", w_x: W_U8) -> W_I32:
    return W_I32(w_x.value)


@OP.builtin_func
def w_i32_to_u32(vm: "SPyVM", w_x: W_I32) -> W_U32:
    return W_U32(w_x.value)


@OP.builtin_func
def w_u32_to_i32(vm: "SPyVM", w_x: W_U32) -> W_I32:
    return W_I32(w_x.value)


@OP.builtin_func
def w_f64_to_i32(vm: "SPyVM", w_x: W_F64) -> W_I32:
    i32_MAX = 2**31 - 1
    val = vm.unwrap_f64(w_x)
    if val > i32_MAX:
        val = i32_MAX
    elif math.isnan(val):
        val = 0
    return vm.wrap(int(val))


@OP.builtin_func(color="blue")
def w_from_dynamic(vm: "SPyVM", w_T: W_Type) -> W_Dynamic:
    """
    Generic function to convert `dynamic` to arbitrary types:
        a: dynamic = ...
        b: i32 = from_dynamic[i32](a)
    """
    T = Annotated[W_Object, w_T]

    # operator::from_dynamic[i32]
    @vm.register_builtin_func("operator", "from_dynamic", [w_T.fqn])
    def w_from_dynamic_T(vm: "SPyVM", w_obj: W_Dynamic) -> T:
        # XXX, we can probably generate better errors
        #
        # XXX, we should probably try to *convert* w_obj to w_T, instead of
        # just typechecking. E.g.:
        #     a: dynamic = 42
        #     b: f64 = from_dynamic[f64](a)  # this should work
        vm.typecheck(w_obj, w_T)
        return w_obj

    return w_from_dynamic_T


MM.register("convert", "i8", "f64", OP.w_i8_to_f64)
MM.register("convert", "u8", "f64", OP.w_u8_to_f64)
MM.register("convert", "i32", "f64", OP.w_i32_to_f64)
MM.register("convert", "u32", "f64", OP.w_u32_to_f64)
MM.register("convert", "i32", "bool", OP.w_i32_to_bool)

# this is wrong: we don't want implicit truncation from float to int. Maybe
# eventually we will want a distinction between implicit and explicit
# conversions?
# MM.register('convert', 'f64', 'i32', OP.w_f64_to_i32)

# XXX: we need to think about conversion rules between int types. The
# following enabled C-style conversion, in which we implicitly convert
# e.g. i32 into i8.  Maybe we should take the rust route and disallow it, but
# this probably requires to introduce a new type "literal".
MM.register("convert", "i32", "i8", OP.w_i32_to_i8)
MM.register("convert", "i8", "i32", OP.w_i8_to_i32)
MM.register("convert", "i32", "u8", OP.w_i32_to_u8)
MM.register("convert", "u8", "i32", OP.w_u8_to_i32)
MM.register("convert", "i32", "u32", OP.w_i32_to_u32)
MM.register("convert", "u32", "i32", OP.w_u32_to_i32)
