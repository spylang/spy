"""
Poor man's implementation of multimethods.
"""
from typing import Optional
from spy.vm.b import B
from spy.vm.object import W_Type, W_Object
from spy.vm.function import W_Func

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
                 w_impl: W_Object) -> None:
        assert isinstance(w_impl, W_Func)
        w_ltype = parse_type(ltype)
        w_rtype = parse_type(rtype)
        key = (op, w_ltype, w_rtype)
        assert key not in self.impls
        self.impls[key] = w_impl

    def lookup(self, op: str, w_ltype: W_Type, w_rtype: W_Type) -> W_Object:
        key = (op, w_ltype, w_rtype)
        return self.impls.get(key, B.w_NotImplemented)
