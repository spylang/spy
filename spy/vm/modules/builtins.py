"""
Second half of the `builtins` module.

The first half is in vm/b.py. See its docstring for more details.
"""

from typing import TYPE_CHECKING
from spy.errors import SPyError
from spy.vm.builtin import builtin_func
from spy.vm.primitive import W_F64, W_I32, W_Bool, W_Dynamic, W_NoneType
from spy.vm.opimpl import W_OpArg, W_OpImpl
from spy.vm.object import W_Object, W_Type
from spy.vm.str import W_Str
from spy.vm.function import W_FuncType
from spy.vm.b import BUILTINS, B

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

PY_PRINT = print  # type: ignore

@BUILTINS.builtin_func(color='blue')
def w_STATIC_TYPE(vm: 'SPyVM', w_expr: W_Object) -> W_Type:
    msg = ("STATIC_TYPE should never be called at runtime. "
           "It's special-cased by ASTFrame")
    raise NotImplementedError(msg)

@BUILTINS.builtin_func
def w_abs(vm: 'SPyVM', w_x: W_I32) -> W_I32:
    x = vm.unwrap_i32(w_x)
    res = vm.ll.call('spy_builtins$abs', x)
    return vm.wrap(res) # type: ignore

@BUILTINS.builtin_func
def w_max(vm: 'SPyVM', w_x: W_I32, w_y: W_I32) -> W_I32:
    x = vm.unwrap_i32(w_x)
    y = vm.unwrap_i32(w_y)
    res = vm.ll.call('spy_builtins$max', x, y)
    return vm.wrap(res) # type: ignore

@BUILTINS.builtin_func
def w_min(vm: 'SPyVM', w_x: W_I32, w_y: W_I32) -> W_I32:
    x = vm.unwrap_i32(w_x)
    y = vm.unwrap_i32(w_y)
    res = vm.ll.call('spy_builtins$min', x, y)
    return vm.wrap(res) # type: ignore


@BUILTINS.builtin_func(color='blue', kind='metafunc')
def w_print(vm: 'SPyVM', wop_obj: W_OpArg) -> W_OpImpl:
    w_type = wop_obj.w_static_type
    if w_type is B.w_i32:
        return W_OpImpl(B.w_print_i32)
    elif w_type is B.w_f64:
        return W_OpImpl(B.w_print_f64)
    elif w_type is B.w_bool:
        return W_OpImpl(B.w_print_bool)
    elif w_type is B.w_NoneType:
        return W_OpImpl(B.w_print_NoneType)
    elif w_type is B.w_str:
        return W_OpImpl(B.w_print_str)
    elif w_type is B.w_dynamic:
        return W_OpImpl(B.w_print_dynamic)
    elif w_type is B.w_type:
        return W_OpImpl(B.w_print_type)


    else:
        # ???
        return W_OpImpl(B.w_print_dynamic)

    t = w_type.fqn.human_name
    raise SPyError.simple(
        'W_TypeError',
        f'cannot call print(`{t}`)',
        f'this is `{t}`',
        wop_obj.loc
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
def w_print_type(vm: 'SPyVM', w_x: W_Type) -> None:
    PY_PRINT(str(w_x))

@BUILTINS.builtin_func(color='blue', kind='metafunc')
def w_len(vm: 'SPyVM', wop_obj: W_OpArg) -> W_OpImpl:
    from spy.vm.modules.operator import op_fast_call
    w_type = wop_obj.w_static_type

    if w_LEN := w_type.lookup_blue_func('__LEN__'):
        w_opimpl = op_fast_call(vm, w_LEN, [wop_obj])
        return w_opimpl
    elif w_fn := w_type.lookup_func('__len__'):
        w_opimpl = W_OpImpl(w_fn, [wop_obj])
        return w_opimpl

    t = w_type.fqn.human_name
    raise SPyError.simple(
        'W_TypeError',
        f'cannot call len(`{t}`)',
        f'this is `{t}`',
        wop_obj.loc
    )


# this should belong to function.py, but we cannot put it there because of
# circular import issues
@builtin_func('builtins')
def w_functype_eq(vm: 'SPyVM', w_ft1: W_FuncType, w_ft2: W_FuncType) -> W_Bool:
    return vm.wrap(w_ft1 == w_ft2)  # type: ignore


# add aliases for common types. For now we map:
#   int -> i32
#   float -> f64
#
# We might want to map int to different concrete types, depending on the
# platform? Or maybe have some kind of "configure step"?
BUILTINS.add('int', BUILTINS.w_i32)
BUILTINS.add('float', BUILTINS.w_f64)
