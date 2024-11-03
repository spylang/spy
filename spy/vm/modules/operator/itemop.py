from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Type, W_Dynamic
from spy.vm.opimpl import W_OpImpl, W_OpArg

from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@OP.builtin_func(color='blue')
def w_GETITEM(vm: 'SPyVM', wop_obj: W_OpArg, wop_i: W_OpArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opimpl
    w_opimpl = W_OpImpl.NULL
    pyclass = wop_obj.w_static_type.pyclass
    if pyclass.has_meth_overriden('op_GETITEM'):
        w_opimpl = pyclass.op_GETITEM(vm, wop_obj, wop_i)

    typecheck_opimpl(
        vm,
        w_opimpl,
        [wop_obj, wop_i],
        dispatch = 'single',
        errmsg = 'cannot do `{0}`[...]'
    )
    return w_opimpl


@OP.builtin_func(color='blue')
def w_SETITEM(vm: 'SPyVM', wop_obj: W_OpArg, wop_i: W_OpArg,
            wop_v: W_OpArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opimpl
    w_opimpl = W_OpImpl.NULL
    pyclass = wop_obj.w_static_type.pyclass
    if pyclass.has_meth_overriden('op_SETITEM'):
        w_opimpl = pyclass.op_SETITEM(vm, wop_obj, wop_i, wop_v)

    typecheck_opimpl(
        vm,
        w_opimpl,
        [wop_obj, wop_i, wop_v],
        dispatch = 'single',
        errmsg = "cannot do `{0}[`{1}`] = ..."
    )
    return w_opimpl
