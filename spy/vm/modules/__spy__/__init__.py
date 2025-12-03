"""
SPy `__spy__` module.
"""

from typing import TYPE_CHECKING

from spy.vm.b import B
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
