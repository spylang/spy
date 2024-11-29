from typing import TYPE_CHECKING, Annotated, Optional
from spy.errors import SPyTypeError
from spy.vm.b import B
from spy.vm.modules.jsffi import JSFFI
from spy.vm.modules.operator import OP
from spy.vm.object import W_Type, W_Object
from spy.vm.function import W_Func, W_FuncType
from spy.vm.opimpl import W_OpArg
from spy.vm.primitive import W_I32, W_F64, W_Bool, W_Dynamic
from spy.vm.builtin import builtin_func
from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin_func(color='blue')
def w_CONVERT(vm: 'SPyVM', w_exp: W_Type, wop_x: W_OpArg) -> W_Func:
    """
    Return a w_func which can convert the given OpArg to the desired type.

    If the types are not compatible, raise SPyTypeError. In this case,
    the caller can catch the error, add extra info and re-raise.
    """
    w_got = wop_x.w_static_type

    # this condition is checked by CONVERT_maybe. If we want this function to
    # become more generally usable, we might want to return an identity func
    # here.
    assert not vm.issubclass(w_got, w_exp)

    if vm.issubclass(w_exp, w_got):
        # this handles two separate cases:
        #   - upcasts, e.g. object->i32: in this case we just do a typecheck
        #   - dynamic->*: in this case we SHOULD do actual conversions, but at
        #                 the moment we don't so we conflate the two cases
        #                 into one
        w_from_dynamic_T = vm.call(OP.w_from_dynamic, [w_exp])
        return w_from_dynamic_T

    # XXX move this dictionary somewhere else
    converters_w = {
        (B.w_i32, B.w_f64): OP.w_i32_to_f64,
        (B.w_i32, B.w_bool): OP.w_i32_to_bool
    }
    key = (w_got, w_exp)
    w_conv = converters_w.get(key)
    if w_conv is not None:
        return w_conv

    if w_exp is JSFFI.w_JsRef:
        if w_conv := convert_JsRef_maybe(w_got, w_exp):
            return w_conv

    # mismatched types
    err = SPyTypeError('mismatched types')
    got = w_got.fqn.human_name
    exp = w_exp.fqn.human_name
    err.add('error', f'expected `{exp}`, got `{got}`', loc=wop_x.loc)
    raise err


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
    return vm.call(OP.w_CONVERT, [w_exp, wop_x])

def convert_JsRef_maybe(w_got: W_Type, w_exp: W_Type) -> Optional[W_Func]:
    if w_got is B.w_str:
        return JSFFI.w_js_string
    elif w_got is B.w_i32:
        return JSFFI.w_js_i32
    elif isinstance(w_got, W_FuncType):
        assert w_got == W_FuncType.parse('def() -> void')
        return JSFFI.w_js_wrap_func
    else:
        return None




@OP.builtin_func
def w_i32_to_f64(vm: 'SPyVM', w_x: W_I32) -> W_F64:
    val = vm.unwrap_i32(w_x)
    return vm.wrap(float(val))

@OP.builtin_func
def w_i32_to_bool(vm: 'SPyVM', w_x: W_I32) -> W_Bool:
    val = vm.unwrap_i32(w_x)
    return vm.wrap(bool(val))


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
