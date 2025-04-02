"""
Poor man's implementation of multimethods.

This uses a super simple logic: we keep a table of ('op', ltype, rtype) and we
do precise lookups. For now, there is no support for implicit conversions,
supertypes, etc.

When registering an opimpl, you can specify only one of the two types, leaving
the other as `None`. During lookup, we first try a precise lookup, and the one
of the two partial ones, in order.

E.g.:
    MM.register('+', 'dynamic', None, OP.w_dynamic_add)
    MM.register('+', None, 'dynamic', OP.w_dynamic_add)

will call w_dynamic_add as long as one of the two operands is 'dynamic'.
"""
from typing import Optional, TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Type, W_Object
from spy.vm.function import W_Func
from spy.vm.opimpl import W_OpImpl, W_OpArg
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

KeyType = tuple[str, Optional[W_Type], Optional[W_Type]]

def parse_type(s: Optional[str]) -> Optional[W_Type]:
    if s is None:
        return None
    w_res = getattr(B, f'w_{s}')
    assert isinstance(w_res, W_Type)
    return w_res

class MultiMethodTable:
    impls: dict[KeyType, W_Func]

    def __init__(self) -> None:
        self.impls = {}

    def register(self,
                 op: str,
                 ltype: Optional[str],
                 rtype: Optional[str],
                 w_func: W_Object) -> None:
        assert isinstance(w_func, W_Func)
        w_ltype = parse_type(ltype)
        w_rtype = parse_type(rtype)
        key = (op, w_ltype, w_rtype)
        assert key not in self.impls
        self.impls[key] = w_func

    def register_partial(self, op: str, atype: str, w_func: W_Object) -> None:
        self.register(op, atype, None, w_func)
        self.register(op, None, atype, w_func)

    def lookup(self, op: str, w_ltype: W_Type, w_rtype: W_Type) -> W_OpImpl:
        keys = [
            (op, w_ltype, w_rtype),  # most precise lookup
            (op, w_ltype, None),     # less precise ones
            (op, None,    w_rtype),
        ]
        for key in keys:
            w_func = self.impls.get(key)
            if w_func:
                return W_OpImpl(w_func)
        return W_OpImpl.NULL

    def get_opimpl(self, vm: 'SPyVM', op: str,
                   wop_l: W_OpArg, wop_r: W_OpArg) -> W_Func:
        from spy.vm.typechecker import typecheck_opimpl
        w_ltype = wop_l.w_static_type
        w_rtype = wop_r.w_static_type
        w_opimpl = self.lookup(op, w_ltype, w_rtype)
        return typecheck_opimpl(
            vm,
            w_opimpl,
            [wop_l, wop_r],
            dispatch = 'multi',
            errmsg = 'cannot do `{0}` %s `{1}`' % op
        )

    def get_unary_opimpl(self, vm: 'SPyVM', op: str,
                         wop_v: W_OpArg) -> W_Func:
        from spy.vm.typechecker import typecheck_opimpl
        w_vtype = wop_v.w_static_type
        w_opimpl = self.lookup(op, w_vtype, None)
        return typecheck_opimpl(
            vm,
            w_opimpl,
            [wop_v],
            dispatch = 'single',
            errmsg = 'cannot do %s`{0}`' % op
        )
