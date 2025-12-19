"""
SPy `__spy__` module.
"""

from typing import TYPE_CHECKING, Annotated, Any

from spy.errors import SPyError
from spy.vm.b import B
from spy.vm.builtin import builtin_method
from spy.vm.object import W_Object
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_Bool
from spy.vm.registry import ModuleRegistry

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

SPY = ModuleRegistry("__spy__")

from . import (
    interp_list,  # noqa: F401 -- side effects
)


@SPY.builtin_func
def w_is_compiled(vm: "SPyVM") -> W_Bool:
    return B.w_False


@SPY.builtin_func("__INIT__", color="blue")
def w_INIT(vm: "SPyVM") -> None:
    for w_listtype in interp_list.PREBUILT_INTERP_LIST_TYPES.values():
        w_listtype.register_push_function(vm)


@SPY.builtin_type("EmptyListType")
class W_EmptyListType(W_Object):
    """
    An object representing '[]'
    """

    def __init__(self) -> None:
        # just a sanity check, W_EmptyList is a singleton
        raise Exception("You cannot instantiate W_EmptyListType")

    def __repr__(self) -> str:
        return "<spy empty_list []>"

    def spy_unwrap(self, vm: "SPyVM") -> Any:
        return []

    @builtin_method("__call_method__", color="blue", kind="metafunc")
    @staticmethod
    def w_CALL_METHOD(
        vm: "SPyVM",
        wam_self: "W_MetaArg",
        wam_name: "W_MetaArg",
        *args_wam: "W_MetaArg",
    ) -> "W_OpSpec":
        name = wam_name.blue_unwrap_str(vm)
        if name in ("append", "extend", "insert"):
            err = SPyError("W_TypeError", "cannot mutate an untyped empty list")
            err.add("error", "this is untyped", wam_self.loc)
            if sym := wam_self.sym:
                err.add(
                    "note",
                    f"help: use an explicit type: `{sym.name}: list[T] = []`",
                    sym.loc,
                )
            raise err
        return W_OpSpec.NULL


SPY.add("empty_list", W_EmptyListType.__new__(W_EmptyListType))
