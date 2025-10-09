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

from typing import TYPE_CHECKING, Optional

from spy.vm.b import B
from spy.vm.function import W_Func
from spy.vm.object import W_Object, W_Type
from spy.vm.opimpl import W_OpImpl
from spy.vm.opspec import W_MetaArg, W_OpSpec

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

KeyType = tuple[str, Optional[W_Type], Optional[W_Type]]


def parse_type(s: Optional[str]) -> Optional[W_Type]:
    if s is None:
        return None
    w_res = getattr(B, f"w_{s}")
    assert isinstance(w_res, W_Type)
    return w_res


class MultiMethodTable:
    impls: dict[KeyType, W_Func]

    def __init__(self) -> None:
        self.impls = {}

    def register(
        self, op: str, ltype: Optional[str], rtype: Optional[str], w_func: W_Object
    ) -> None:
        assert isinstance(w_func, W_Func)
        w_ltype = parse_type(ltype)
        w_rtype = parse_type(rtype)
        key = (op, w_ltype, w_rtype)
        assert key not in self.impls
        self.impls[key] = w_func

    def register_partial(self, op: str, atype: str, w_func: W_Object) -> None:
        self.register(op, atype, None, w_func)
        self.register(op, None, atype, w_func)

    def lookup(
        self, op: str, w_ltype: Optional[W_Type], w_rtype: Optional[W_Type]
    ) -> Optional[W_OpSpec]:
        keys = [
            (op, w_ltype, w_rtype),  # most precise lookup
            (op, w_ltype, None),  # less precise ones
            (op, None, w_rtype),
        ]
        for key in keys:
            w_func = self.impls.get(key)
            if w_func:
                return W_OpSpec(w_func)
        return None

    def get_unary_opspec(self, op: str, wam_v: W_MetaArg) -> Optional[W_OpSpec]:
        w_vtype = wam_v.w_static_T
        return self.lookup(op, w_vtype, None)

    def get_binary_opspec(
        self, op: str, wam_l: W_MetaArg, wam_r: W_MetaArg
    ) -> Optional[W_OpSpec]:
        w_ltype = wam_l.w_static_T
        w_rtype = wam_r.w_static_T
        return self.lookup(op, w_ltype, w_rtype)
