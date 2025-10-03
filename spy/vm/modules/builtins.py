"""
Second half of the `builtins` module.

The first half is in vm/b.py. See its docstring for more details.
"""

from typing import TYPE_CHECKING
from spy.errors import SPyError
from spy.vm.primitive import W_F64, W_I32, W_Bool, W_Dynamic, W_NoneType
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.object import W_Object, W_Type
from spy.vm.str import W_Str
from spy.vm.function import W_FuncType
from spy.vm.b import BUILTINS, B

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

PY_PRINT = print  # type: ignore

@BUILTINS.builtin_func(color='blue', kind='metafunc')
def w_STATIC_TYPE(vm: 'SPyVM', wam_obj: W_MetaArg) -> W_OpSpec:
    return W_OpSpec.const(wam_obj.w_static_T)

@BUILTINS.builtin_func
def w_abs(vm: 'SPyVM', w_x: W_I32) -> W_I32:
    x = vm.unwrap_i32(w_x)
    res = vm.ll.call('spy_builtins$abs', x)
    return vm.wrap(res)

@BUILTINS.builtin_func
def w_max(vm: 'SPyVM', w_x: W_I32, w_y: W_I32) -> W_I32:
    x = vm.unwrap_i32(w_x)
    y = vm.unwrap_i32(w_y)
    res = vm.ll.call('spy_builtins$max', x, y)
    return vm.wrap(res)

@BUILTINS.builtin_func
def w_min(vm: 'SPyVM', w_x: W_I32, w_y: W_I32) -> W_I32:
    x = vm.unwrap_i32(w_x)
    y = vm.unwrap_i32(w_y)
    res = vm.ll.call('spy_builtins$min', x, y)
    return vm.wrap(res)


@BUILTINS.builtin_func(color='blue', kind='metafunc')
def w_print(vm: 'SPyVM', wam_obj: W_MetaArg) -> W_OpSpec:
    w_T = wam_obj.w_static_T
    if w_T is B.w_i32:
        return W_OpSpec(B.w_print_i32)
    elif w_T is B.w_f64:
        return W_OpSpec(B.w_print_f64)
    elif w_T is B.w_bool:
        return W_OpSpec(B.w_print_bool)
    elif w_T is B.w_NoneType:
        return W_OpSpec(B.w_print_NoneType)
    elif w_T is B.w_str:
        return W_OpSpec(B.w_print_str)
    elif w_T is B.w_dynamic:
        return W_OpSpec(B.w_print_dynamic)

    elif wam_obj.color == 'blue':
        # if we print something of unsupported type BUT it's a blue object, we
        # can precompute its repr now and just print it as a string. This
        # allows to print things like types even with the C backend.
        s = str(wam_obj.w_blueval)
        wam_s = W_MetaArg.from_w_obj(vm, vm.wrap(s))
        return W_OpSpec(w_print_str, [wam_s])

    else:
        # printing a red value of unsupported type. As a fallback, we just use
        # w_print_object, but this will not work in the C backend.
        return W_OpSpec(B.w_print_object)

    t = w_T.fqn.human_name
    raise SPyError.simple(
        'W_TypeError',
        f'cannot call print(`{t}`)',
        f'this is `{t}`',
        wam_obj.loc
    )


@BUILTINS.builtin_func
def w_print_i32(vm: 'SPyVM', w_x: W_I32) -> None:
    PY_PRINT(vm.unwrap(w_x))

@BUILTINS.builtin_func
def w_print_f64(vm: 'SPyVM', w_x: W_F64) -> None:
    PY_PRINT(vm.unwrap(w_x))

@BUILTINS.builtin_func
def w_print_bool(vm: 'SPyVM', w_x: W_Bool) -> None:
    PY_PRINT(vm.unwrap(w_x))

@BUILTINS.builtin_func
def w_print_NoneType(vm: 'SPyVM', w_x: W_NoneType) -> None:
    PY_PRINT(vm.unwrap(w_x))

@BUILTINS.builtin_func
def w_print_str(vm: 'SPyVM', w_x: W_Str) -> None:
    PY_PRINT(vm.unwrap(w_x))

@BUILTINS.builtin_func
def w_print_dynamic(vm: 'SPyVM', w_x: W_Dynamic) -> None:
    PY_PRINT(vm.unwrap(w_x))

@BUILTINS.builtin_func
def w_print_object(vm: 'SPyVM', w_x: W_Object) -> None:
    PY_PRINT(str(w_x))

@BUILTINS.builtin_func(color='blue', kind='metafunc')
def w_len(vm: 'SPyVM', wam_obj: W_MetaArg) -> W_OpSpec:
    w_T = wam_obj.w_static_T
    if w_fn := w_T.lookup_func('__len__'):
        w_opspec = vm.fast_metacall(w_fn, [wam_obj])
        return w_opspec

    t = w_T.fqn.human_name
    raise SPyError.simple(
        'W_TypeError',
        f'cannot call len(`{t}`)',
        f'this is `{t}`',
        wam_obj.loc
    )

# add aliases for common types. For now we map:
#   int -> i32
#   float -> f64
#
# We might want to map int to different concrete types, depending on the
# platform? Or maybe have some kind of "configure step"?
BUILTINS.add('int', BUILTINS.w_i32)
BUILTINS.add('float', BUILTINS.w_f64)
