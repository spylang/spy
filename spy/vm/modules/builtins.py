"""
Second half of the `builtins` module.

The first half is in vm/b.py. See its docstring for more details.
"""

from typing import TYPE_CHECKING

from spy.errors import SPyError
from spy.vm.b import BUILTINS, TYPES, B
from spy.vm.function import W_FuncType
from spy.vm.modules.__spy__.interp_list import (
    W_StrInterpList,
    make_str_interp_list,
    w_str_interp_list_type,
)
from spy.vm.object import W_Object, W_Type
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_F64, W_I8, W_I32, W_U8, W_Bool, W_Dynamic, W_NoneType
from spy.vm.str import W_Str

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

PY_PRINT = print  # type: ignore


@BUILTINS.builtin_func(color="blue", kind="metafunc")
def w_STATIC_TYPE(vm: "SPyVM", wam_obj: W_MetaArg) -> W_OpSpec:
    return W_OpSpec.const(wam_obj.w_static_T)


@BUILTINS.builtin_func
def w_abs(vm: "SPyVM", w_x: W_I32) -> W_I32:
    x = vm.unwrap_i32(w_x)
    res = vm.ll.call("spy_builtins$abs", x)
    return vm.wrap(res)


@BUILTINS.builtin_func
def w_max(vm: "SPyVM", w_x: W_I32, w_y: W_I32) -> W_I32:
    x = vm.unwrap_i32(w_x)
    y = vm.unwrap_i32(w_y)
    res = vm.ll.call("spy_builtins$max", x, y)
    return vm.wrap(res)


@BUILTINS.builtin_func
def w_min(vm: "SPyVM", w_x: W_I32, w_y: W_I32) -> W_I32:
    x = vm.unwrap_i32(w_x)
    y = vm.unwrap_i32(w_y)
    res = vm.ll.call("spy_builtins$min", x, y)
    return vm.wrap(res)


@BUILTINS.builtin_func(color="blue", kind="metafunc")
def w_print(vm: "SPyVM", wam_obj: W_MetaArg) -> W_OpSpec:
    w_T = wam_obj.w_static_T
    if w_T is B.w_i32:
        return W_OpSpec(B.w_print_i32)
    elif w_T is B.w_f64:
        return W_OpSpec(B.w_print_f64)
    elif w_T is B.w_bool:
        return W_OpSpec(B.w_print_bool)
    elif w_T is TYPES.w_NoneType:
        return W_OpSpec(B.w_print_NoneType)
    elif w_T is B.w_str:
        return W_OpSpec(B.w_print_str)
    elif w_T is B.w_dynamic:
        return W_OpSpec(B.w_print_dynamic)

    elif wam_obj.color == "blue":
        # if we print something of unsupported type BUT it's a blue object, we
        # can precompute its repr now and just print it as a string. This
        # allows to print things like types even with the C backend.
        wam_s = vm.str_wam(wam_obj, loc=wam_obj.loc)
        return W_OpSpec(w_print_str, [wam_s])

    else:
        # printing a red value of unsupported type. As a fallback, we just use
        # w_print_object, but this will not work in the C backend.
        return W_OpSpec(B.w_print_object)

    t = w_T.fqn.human_name
    raise SPyError.simple(
        "W_TypeError", f"cannot call print(`{t}`)", f"this is `{t}`", wam_obj.loc
    )


@BUILTINS.builtin_func
def w_print_i32(vm: "SPyVM", w_x: W_I32) -> None:
    PY_PRINT(vm.unwrap(w_x))


@BUILTINS.builtin_func
def w_print_f64(vm: "SPyVM", w_x: W_F64) -> None:
    PY_PRINT(vm.unwrap(w_x))


@BUILTINS.builtin_func
def w_print_bool(vm: "SPyVM", w_x: W_Bool) -> None:
    PY_PRINT(vm.unwrap(w_x))


@BUILTINS.builtin_func
def w_print_NoneType(vm: "SPyVM", w_x: W_NoneType) -> None:
    PY_PRINT(vm.unwrap(w_x))


@BUILTINS.builtin_func
def w_print_str(vm: "SPyVM", w_x: W_Str) -> None:
    PY_PRINT(vm.unwrap(w_x))


@BUILTINS.builtin_func
def w_print_dynamic(vm: "SPyVM", w_x: W_Dynamic) -> None:
    PY_PRINT(vm.unwrap(w_x))


@BUILTINS.builtin_func
def w_print_object(vm: "SPyVM", w_x: W_Object) -> None:
    PY_PRINT(str(w_x))


@BUILTINS.builtin_func(color="blue", kind="metafunc")
def w_len(vm: "SPyVM", wam_obj: W_MetaArg) -> W_OpSpec:
    w_T = wam_obj.w_static_T
    if w_fn := w_T.lookup_func("__len__"):
        w_opspec = vm.fast_metacall(w_fn, [wam_obj])
        return w_opspec

    t = w_T.fqn.human_name
    raise SPyError.simple(
        "W_TypeError", f"cannot call len(`{t}`)", f"this is `{t}`", wam_obj.loc
    )


@BUILTINS.builtin_func(color="blue", kind="metafunc")
def w_repr(vm: "SPyVM", wam_obj: W_MetaArg) -> W_OpSpec:
    w_T = wam_obj.w_static_T
    if w_fn := w_T.lookup_func("__repr__"):
        w_opspec = vm.fast_metacall(w_fn, [wam_obj])
        return w_opspec

    # this can happen only if you override a __repr__ which returns
    # OpSpec.NULL
    t = w_T.fqn.human_name
    raise SPyError.simple(
        "W_TypeError", f"cannot call repr(`{t}`)", f"this is `{t}`", wam_obj.loc
    )


@BUILTINS.builtin_func
def w_hash_i8(vm: "SPyVM", w_x: W_I8) -> W_I32:
    x = vm.unwrap_i8(w_x)
    if x == -1:
        return vm.wrap(2)
    return vm.wrap(x)


@BUILTINS.builtin_func
def w_hash_i32(vm: "SPyVM", w_x: W_I32) -> W_I32:
    if (vm.unwrap_i32(w_x)) == -1:
        return vm.wrap(2)
    return w_x


@BUILTINS.builtin_func
def w_hash_u8(vm: "SPyVM", w_x: W_U8) -> W_I32:
    return vm.wrap(vm.unwrap_u8(w_x))


@BUILTINS.builtin_func
def w_hash_bool(vm: "SPyVM", w_x: W_Bool) -> W_I32:
    if w_x is B.w_False:
        return vm.wrap(0)
    elif w_x is B.w_True:
        return vm.wrap(1)
    else:
        assert False, "unreachable"


@BUILTINS.builtin_func
def w_hash_str(vm: "SPyVM", w_x: W_Str) -> W_I32:
    assert isinstance(w_x, W_Str)
    res = vm.ll.call("spy_str_hash", w_x.ptr)
    return vm.wrap(res)


@BUILTINS.builtin_func(color="blue", kind="metafunc")
def w_hash(vm: "SPyVM", wam_obj: W_MetaArg) -> W_OpSpec:
    w_T = wam_obj.w_static_T
    if w_T is B.w_i8:
        return W_OpSpec(B.w_hash_i8)
    elif w_T is B.w_i32:
        return W_OpSpec(B.w_hash_i32)
    elif w_T is B.w_u8:
        return W_OpSpec(B.w_hash_u8)
    elif w_T is B.w_bool:
        return W_OpSpec(B.w_hash_bool)
    elif w_T is B.w_str:
        return W_OpSpec(B.w_hash_str)

    if w_fn := w_T.lookup_func("__hash__"):
        w_opspec = vm.fast_metacall(w_fn, [wam_obj])
        return w_opspec

    t = w_T.fqn.human_name
    raise SPyError.simple(
        "W_TypeError", f"unhashable type '{t}'", f"this is `{t}`", wam_obj.loc
    )


# w_dir is a metafunc because we can precompute the result at blue time
@BUILTINS.builtin_func(color="blue", kind="metafunc")
def w_dir(vm: "SPyVM", wam_obj: W_MetaArg) -> W_OpSpec:
    # get the names from the type
    w_T = wam_obj.w_static_T
    names = w_T.spy_dir(vm)

    # get the names from the instance, if it's blue
    if wam_obj.color == "blue":
        new_names = wam_obj.w_blueval.spy_dir(vm)
        names.update(new_names)

    names_w = [vm.wrap(name) for name in sorted(names)]
    w_names = make_str_interp_list(names_w)
    return W_OpSpec.const(w_names)


@BUILTINS.builtin_func(color="blue", kind="metafunc")
def w_getattr(vm: "SPyVM", wam_obj: W_MetaArg, wam_name: W_MetaArg) -> W_OpSpec:
    # ensure that wam_name is blue; raise TypeError if not
    name = wam_name.blue_unwrap_str(vm)

    @vm.register_builtin_func("builtins", "getattr", [name])
    def w_fn(vm: "SPyVM", w_obj: W_Object, w_name: W_Str) -> W_Object:
        assert False, (
            "this function shouldn't be called, it's special cased by astframe"
        )

    return W_OpSpec(w_fn)


@BUILTINS.builtin_func(color="blue", kind="metafunc")
def w_setattr(
    vm: "SPyVM", wam_obj: W_MetaArg, wam_name: W_MetaArg, wam_value: W_MetaArg
) -> W_OpSpec:
    # ensure that wam_name is blue; raise TypeError if not
    name = wam_name.blue_unwrap_str(vm)

    @vm.register_builtin_func("builtins", "getattr", [name])
    def w_fn(vm: "SPyVM", w_obj: W_Object, w_name: W_Str, w_val: W_Object) -> W_Object:
        assert False, (
            "this function shouldn't be called, it's special cased by astframe"
        )

    return W_OpSpec(w_fn)


# add aliases for common types. For now we map:
#   int -> i32
#   float -> f64
#
# We might want to map int to different concrete types, depending on the
# platform? Or maybe have some kind of "configure step"?
BUILTINS.add("int", BUILTINS.w_i32)
BUILTINS.add("float", BUILTINS.w_f64)
