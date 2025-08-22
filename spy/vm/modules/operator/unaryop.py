from typing import TYPE_CHECKING
from spy.vm.opspec import W_OpArg
from spy.vm.opimpl import W_OpImpl
from . import OP
from .multimethod import MultiMethodTable
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

MM = MultiMethodTable()

@OP.builtin_func(color='blue')
def w_NEG(vm: 'SPyVM', wop_v: W_OpArg) -> W_OpImpl:
    from spy.vm.typechecker import typecheck_opspec
    w_vtype = wop_v.w_static_T
    if w_neg := w_vtype.lookup_func('__neg__'):
        w_opspec = vm.fast_metacall(w_neg, [wop_v])
        return typecheck_opspec(vm, w_opspec, [wop_v],
                                dispatch='single',
                                errmsg='cannot do -`{0}`')
    return MM.get_unary_opimpl(vm, '-', wop_v)

MM.register('-', 'i8',  None, OP.w_i8_neg)
MM.register('-', 'i32', None, OP.w_i32_neg)
MM.register('-', 'f64', None, OP.w_f64_neg)
