from typing import TYPE_CHECKING, Annotated
from spy.vm.b import B
from spy.vm.object import W_Type, W_Object
from spy.vm.function import W_Func
from spy.vm.primitive import W_I32, W_F64, W_Bool, W_Dynamic
from spy.vm.builtin import builtin_func
from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


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
