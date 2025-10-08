from typing import TYPE_CHECKING, Any

from spy.vm.b import B
from spy.vm.builtin import builtin_method
from spy.vm.object import W_Object
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_I32, W_Bool, W_Dynamic

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@B.builtin_type("tuple")
class W_Tuple(W_Object):
    """
    This is not the "real" tuple type that we will have in SPy.

    It's a trimmed-down "dynamic" tuple, which can contain an arbitrary number
    of items of arbitrary types. It is meant to be used in blue code, and we
    need it to bootstrap SPy.

    Eventally, it will become a "real" type-safe, generic type.
    """
    __spy_storage_category__ = "value"

    items_w: list[W_Object]

    def __init__(self, items_w: list[W_Object]) -> None:
        self.items_w = items_w

    def spy_unwrap(self, vm: "SPyVM") -> tuple:
        return tuple([vm.unwrap(w_item) for w_item in self.items_w])

    def spy_key(self, vm: "SPyVM") -> Any:
        return tuple(w_item.spy_key(vm) for w_item in self.items_w)

    def __repr__(self) -> str:
        return f"W_Tuple({self.items_w})"

    @builtin_method("__getitem__")
    @staticmethod
    def w_getitem(vm: "SPyVM", w_tup: "W_Tuple", w_i: W_I32) -> W_Dynamic:
        i = vm.unwrap_i32(w_i)
        # XXX bound check?
        return w_tup.items_w[i]

    @builtin_method("__len__")
    @staticmethod
    def w_len(vm: "SPyVM", w_tup: "W_Tuple") -> W_I32:
        n = len(w_tup.items_w)
        return vm.wrap(n)

    @builtin_method("__eq__", color="blue", kind="metafunc")
    @staticmethod
    def w_EQ(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpSpec:
        w_ltype = wam_l.w_static_T
        w_rtype = wam_r.w_static_T
        if w_ltype is not w_rtype:
            return W_OpSpec.NULL

        @vm.register_builtin_func(W_Tuple._w.fqn)
        def w_eq(vm: "SPyVM", w_t1: W_Tuple, w_t2: W_Tuple) -> W_Bool:
            items1_w = w_t1.items_w
            items2_w = w_t2.items_w
            if len(items1_w) != len(items2_w):
                return B.w_False
            for w_1, w_2 in zip(items1_w, items2_w):
                if vm.is_False(vm.eq(w_1, w_2)):
                    return B.w_False
            return B.w_True

        return W_OpSpec(w_eq)
