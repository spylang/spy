from typing import TYPE_CHECKING, Annotated, Optional
from spy.errors import SPyError
from spy.vm.b import B
from spy.vm.modules.jsffi import JSFFI
from spy.vm.modules.operator import OP
from spy.vm.object import W_Type, W_Object
from spy.vm.function import W_Func, W_FuncType
from spy.vm.opimpl import W_OpArg, W_OpImpl
from spy.vm.primitive import W_I32, W_F64, W_Bool, W_Dynamic
from spy.vm.builtin import builtin_func
from . import OP, op_fast_call
from .multimethod import MultiMethodTable
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

MM = MultiMethodTable()

@OP.builtin_func(color='blue')
def w_CONVERT(vm: 'SPyVM', w_exp: W_Type, wop_x: W_OpArg) -> W_Func:
    """
    Return a w_func which can convert the given OpArg to the desired type.

    If the types are not compatible, raise SPyError. In this case,
    the caller can catch the error, add extra info and re-raise.
    """
    w_opimpl = get_opimpl(vm, w_exp, wop_x)
    if not w_opimpl.is_null():
        # XXX: maybe we should return a W_OpImpl?
        return w_opimpl._w_func  # type: ignore

    # mismatched types
    err = SPyError('mismatched types', etype='W_TypeError')
    got = wop_x.w_static_type.fqn.human_name
    exp = w_exp.fqn.human_name
    err.add('error', f'expected `{exp}`, got `{got}`', loc=wop_x.loc)
    raise err


def get_opimpl(vm: 'SPyVM', w_exp: W_Type, wop_x: W_OpArg) -> W_OpImpl:
    # this condition is checked by CONVERT_maybe. If we want this function to
    # become more generally usable, we might want to return an identity func
    # here.
    w_got = wop_x.w_static_type
    assert not vm.issubclass(w_got, w_exp)

    if vm.issubclass(w_exp, w_got):
        # this handles two separate cases:
        #   - upcasts, e.g. object->i32: in this case we just do a typecheck
        #   - dynamic->*: in this case we SHOULD do actual conversions, but at
        #                 the moment we don't so we conflate the two cases
        #                 into one
        w_from_dynamic_T = vm.fast_call(OP.w_from_dynamic, [w_exp])
        assert isinstance(w_from_dynamic_T, W_Func)
        return W_OpImpl(w_from_dynamic_T)

    w_opimpl = MM.lookup('convert', w_got, w_exp)
    if not w_opimpl.is_null():
        return w_opimpl

    if w_CONV_TO := w_got.lookup_blue_func('__CONVERT_TO__'):
        return op_fast_call(vm, w_CONV_TO, [w_exp, wop_x])
    elif w_CONV_FROM := w_exp.lookup_blue_func('__CONVERT_FROM__'):
        return op_fast_call(vm, w_CONV_FROM, [w_got, wop_x])

    return W_OpImpl.NULL


def CONVERT_maybe(
        vm: 'SPyVM', w_exp: W_Type, wop_x: W_OpArg,
) -> Optional[W_Func]:
    """
    Same as w_CONVERT, but return None if the types are already compatible.
    """
    w_got = wop_x.w_static_type
    if vm.issubclass(w_got, w_exp):
        # nothing to do
        return None
    return vm.fast_call(OP.w_CONVERT, [w_exp, wop_x])  # type: ignore

@OP.builtin_func
def w_i32_to_f64(vm: 'SPyVM', w_x: W_I32) -> W_F64:
    val = vm.unwrap_i32(w_x)
    return vm.wrap(float(val))  # type: ignore

@OP.builtin_func
def w_i32_to_bool(vm: 'SPyVM', w_x: W_I32) -> W_Bool:
    val = vm.unwrap_i32(w_x)
    return vm.wrap(bool(val))  # type: ignore

@OP.builtin_func
def w_f64_to_i32(vm: 'SPyVM', w_x: W_F64) -> W_I32:
    val = vm.unwrap_f64(w_x)
    return vm.wrap(int(val))  # type: ignore


@OP.builtin_func(color='blue')
def w_from_dynamic(vm: 'SPyVM', w_T: W_Type) -> W_Dynamic:
    """
    Generic function to convert `dynamic` to arbitrary types:
        a: dynamic = ...
        b: i32 = from_dynamic[i32](a)
    """
    T = Annotated[W_Object, w_T]

    # operator::from_dynamic[i32]
    @builtin_func('operator', 'from_dynamic', [w_T.fqn])
    def w_from_dynamic_T(vm: 'SPyVM', w_obj: W_Dynamic) -> T:
        # XXX, we can probably generate better errors
        #
        # XXX, we should probably try to *convert* w_obj to w_T, instead of
        # just typechecking. E.g.:
        #     a: dynamic = 42
        #     b: f64 = from_dynamic[f64](a)  # this should work
        vm.typecheck(w_obj, w_T)
        return w_obj

    vm.add_global(w_from_dynamic_T.fqn, w_from_dynamic_T)
    return w_from_dynamic_T

MM.register('convert', 'i32', 'f64', OP.w_i32_to_f64)
MM.register('convert', 'i32', 'bool', OP.w_i32_to_bool)
MM.register('convert', 'f64', 'i32', OP.w_f64_to_i32)
