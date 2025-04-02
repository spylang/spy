from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Type
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.function import W_Func
from spy.vm.primitive import W_Dynamic
from . import OP, op_fast_call
from .multimethod import MultiMethodTable
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

MM = MultiMethodTable()

@OP.builtin_func(color='blue')
def w_NEG(vm: 'SPyVM', wop_v: W_OpArg) -> W_Func:
    from spy.vm.typechecker import typecheck_opimpl
    w_vtype = wop_v.w_static_type
    if w_NEG := w_vtype.lookup_blue_func('__NEG__'):
        w_opimpl = op_fast_call(vm, w_NEG, [wop_v])
        return typecheck_opimpl(vm, w_opimpl, [wop_v],
                                dispatch='single',
                                errmsg='cannot do -`{0}`')
    return MM.get_unary_opimpl(vm, '-', wop_v)

MM.register('-', 'i8',  None, OP.w_i8_neg)
MM.register('-', 'i32', None, OP.w_i32_neg)
