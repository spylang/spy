from typing import TYPE_CHECKING, Annotated, Any

from spy.vm.b import B
from spy.vm.builtin import builtin_method
from spy.vm.modules.__spy__ import SPY
from spy.vm.object import W_Object
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_I32, W_Bool, W_Dynamic

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@SPY.builtin_type("interp_tuple_iterator")
class W_InterpTupleIterator(W_Object):
    items_w: list[W_Object]
    i: int

    def __init__(self, items_w: list[W_Object], i: int) -> None:
        self.items_w = items_w
        self.i = i

    def __repr__(self) -> str:
        return f"W_InterpTupleIterator({self.items_w}, {self.i})"

    @builtin_method("__next__")
    @staticmethod
    def w_next(vm: "SPyVM", w_it: "W_InterpTupleIterator") -> "W_InterpTupleIterator":
        return W_InterpTupleIterator(w_it.items_w, w_it.i + 1)

    @builtin_method("__item__")
    @staticmethod
    def w_item(vm: "SPyVM", w_it: "W_InterpTupleIterator") -> W_Dynamic:
        return w_it.items_w[w_it.i]

    @builtin_method("__continue_iteration__")
    @staticmethod
    def w_continue_iteration(vm: "SPyVM", w_it: "W_InterpTupleIterator") -> W_Bool:
        return vm.wrap(w_it.i < len(w_it.items_w))


@SPY.builtin_type("interp_tuple")
class W_InterpTuple(W_Object):
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
        return f"W_InterpTuple({self.items_w})"

    @builtin_method("__new__")
    @staticmethod
    def w_new(vm: "SPyVM", *args_w: W_Object) -> "W_InterpTuple":
        return W_InterpTuple(list(args_w))

    @builtin_method("__fastiter__")
    @staticmethod
    def w_fastiter(
        vm: "SPyVM", w_tup: "W_InterpTuple"
    ) -> Annotated[W_InterpTupleIterator, W_InterpTupleIterator._w]:
        return W_InterpTupleIterator(w_tup.items_w, 0)

    @builtin_method("__getitem__")
    @staticmethod
    def w_getitem(vm: "SPyVM", w_tup: "W_InterpTuple", w_i: W_I32) -> W_Dynamic:
        i = vm.unwrap_i32(w_i)
        # XXX bound check?
        return w_tup.items_w[i]

    @builtin_method("__len__")
    @staticmethod
    def w_len(vm: "SPyVM", w_tup: "W_InterpTuple") -> W_I32:
        n = len(w_tup.items_w)
        return vm.wrap(n)

    @builtin_method("__eq__", color="blue", kind="metafunc")
    @staticmethod
    def w_EQ(vm: "SPyVM", wam_l: W_MetaArg, wam_r: W_MetaArg) -> W_OpSpec:
        w_ltype = wam_l.w_static_T
        w_rtype = wam_r.w_static_T
        if w_ltype is not w_rtype:
            return W_OpSpec.NULL

        @vm.register_builtin_func(W_InterpTuple._w.fqn)
        def w_eq(vm: "SPyVM", w_t1: W_InterpTuple, w_t2: W_InterpTuple) -> W_Bool:
            items1_w = w_t1.items_w
            items2_w = w_t2.items_w
            if len(items1_w) != len(items2_w):
                return B.w_False
            for w_1, w_2 in zip(items1_w, items2_w):
                if vm.is_False(vm.eq_w(w_1, w_2)):
                    return B.w_False
            return B.w_True

        return W_OpSpec(w_eq)
