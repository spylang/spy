from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Type
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.function import W_Func
from spy.vm.primitive import W_Dynamic

from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin_func(color='blue')
def w_GETITEM(vm: 'SPyVM', wop_obj: W_OpArg, wop_i: W_OpArg) -> W_Func:
    from spy.vm.typechecker import typecheck_opimpl
    w_opimpl = W_OpImpl.NULL
    w_type = wop_obj.w_static_type

    w_GETITEM = w_type.lookup_blue_func('__GETITEM__')
    if w_GETITEM:
        w_opimpl = vm.fast_call(w_GETITEM, [wop_obj, wop_i])

    return typecheck_opimpl(
        vm,
        w_opimpl,
        [wop_obj, wop_i],
        dispatch = 'single',
        errmsg = 'cannot do `{0}`[...]'
    )


@OP.builtin_func(color='blue')
def w_SETITEM(vm: 'SPyVM', wop_obj: W_OpArg, wop_i: W_OpArg,
            wop_v: W_OpArg) -> W_Func:
    from spy.vm.typechecker import typecheck_opimpl
    w_opimpl = W_OpImpl.NULL
    w_type = wop_obj.w_static_type

    w_SETITEM = w_type.lookup_blue_func('__SETITEM__')
    if w_SETITEM:
        w_opimpl = vm.fast_call(w_SETITEM, [wop_obj, wop_i, wop_v])

    return typecheck_opimpl(
        vm,
        w_opimpl,
        [wop_obj, wop_i, wop_v],
        dispatch = 'single',
        errmsg = "cannot do `{0}[`{1}`] = ..."
    )
