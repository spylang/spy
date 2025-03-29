from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Type
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.function import W_Func, W_FuncType
from spy.vm.primitive import W_Dynamic

from . import OP, op_fast_call
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin_func(color='blue')
def w_GETITEM(vm: 'SPyVM', wop_obj: W_OpArg, wop_i: W_OpArg) -> W_Func:
    from spy.vm.typechecker import typecheck_opimpl
    w_opimpl = W_OpImpl.NULL
    w_type = wop_obj.w_static_type

    if isinstance(w_type, W_FuncType) and w_type.kind == 'generic':
        # special case: for generic W_Funcs, "[]" means "call"
        w_opimpl = w_type.pyclass.op_CALL(vm, wop_obj, wop_i) # type: ignore
    elif w_GETITEM := w_type.lookup_blue_func('__GETITEM__'):
        w_opimpl = op_fast_call(vm, w_GETITEM, [wop_obj, wop_i])
    elif w_getitem := w_type.lookup_func('__getitem__'):
        w_opimpl = W_OpImpl(w_getitem, [wop_obj, wop_i])

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

    if w_SETITEM := w_type.lookup_blue_func('__SETITEM__'):
        w_opimpl = op_fast_call(vm, w_SETITEM, [wop_obj, wop_i, wop_v])
    elif w_setitem := w_type.lookup_func('__setitem__'):
        w_opimpl = W_OpImpl(w_setitem, [wop_obj, wop_i, wop_v])

    return typecheck_opimpl(
        vm,
        w_opimpl,
        [wop_obj, wop_i, wop_v],
        dispatch = 'single',
        errmsg = "cannot do `{0}[`{1}`] = ..."
    )
