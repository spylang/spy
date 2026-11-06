from typing import TYPE_CHECKING, Annotated, Any

from spy.location import Loc
from spy.vm.builtin import builtin_method, builtin_property
from spy.vm.modules.__spy__ import SPY
from spy.vm.modules.__spy__.interp_tuple import W_InterpTuple
from spy.vm.modules.types import W_Loc
from spy.vm.object import W_Object
from spy.vm.opspec import W_MetaArg
from spy.vm.primitive import W_I32, W_Bool

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@SPY.builtin_type("meta_args_iterator")
class W_MetaArgsIterator(W_Object):
    items_wam: list[W_MetaArg]
    i: int

    def __init__(self, items_wam: list[W_MetaArg], i: int) -> None:
        self.items_wam = items_wam
        self.i = i

    def __repr__(self) -> str:
        return f"W_MetaArgsIterator({self.items_wam}, {self.i})"

    @builtin_method("__next__")
    @staticmethod
    def w_next(vm: "SPyVM", w_it: "W_MetaArgsIterator") -> "W_MetaArgsIterator":
        return W_MetaArgsIterator(w_it.items_wam, w_it.i + 1)

    @builtin_method("__item__")
    @staticmethod
    def w_item(vm: "SPyVM", w_it: "W_MetaArgsIterator") -> W_MetaArg:
        return w_it.items_wam[w_it.i]

    @builtin_method("__continue_iteration__")
    @staticmethod
    def w_continue_iteration(vm: "SPyVM", w_it: "W_MetaArgsIterator") -> W_Bool:
        return vm.wrap(w_it.i < len(w_it.items_wam))


@SPY.builtin_type("meta_args")
class W_MetaArgs(W_InterpTuple):
    """
    The type of `*args_m` in a metafunc.

    It is a trimmed-down tuple of MetaArgs, similar to `interp_tuple`, but
    with two differences:

      - the static type of its items is `MetaArg` (instead of `dynamic`), so
        that e.g. `[args_m[0], args_m[1]]` is a `list[MetaArg]` and `m_x, m_y =
        args_m` declares two `MetaArg` locals.

      - it carries some extra information about the call: `loc` and `types`.

    Like `interp_tuple`, it is meant to be used in blue code only.
    """

    __spy_storage_category__ = "value"

    items_wam: list[W_MetaArg]
    loc: Loc

    def __init__(self, items_wam: list[W_MetaArg], loc: Loc) -> None:
        items_w: list[W_Object] = list(items_wam)
        super().__init__(items_w)
        self.items_wam = items_wam
        self.loc = loc

    def __repr__(self) -> str:
        return f"W_MetaArgs({self.items_wam})"

    def spy_key(self, vm: "SPyVM") -> Any:
        # like for MetaArg, the loc is not part of the key
        return ("MetaArgs", tuple(wam.spy_key(vm) for wam in self.items_wam))

    @builtin_method("__fastiter__")
    @staticmethod
    def w_fastiter(
        vm: "SPyVM", w_self: "W_MetaArgs"
    ) -> Annotated[W_MetaArgsIterator, W_MetaArgsIterator._w]:
        return W_MetaArgsIterator(w_self.items_wam, 0)

    @builtin_method("__getitem__")
    @staticmethod
    def w_getitem(vm: "SPyVM", w_self: "W_MetaArgs", w_i: W_I32) -> W_MetaArg:
        i = vm.unwrap_i32(w_i)
        # XXX bound check?
        return w_self.items_wam[i]

    @builtin_property("loc")
    @staticmethod
    def w_get_loc(vm: "SPyVM", w_self: "W_MetaArgs") -> W_Loc:
        """
        The source location of the arguments.
        """
        return W_Loc(w_self.loc)

    @builtin_property("types")
    @staticmethod
    def w_get_types(vm: "SPyVM", w_self: "W_MetaArgs") -> W_InterpTuple:
        """
        The static types of the arguments, as a tuple.
        """
        return W_InterpTuple([wam.w_static_T for wam in w_self.items_wam])
