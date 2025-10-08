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

@SPY.builtin_func
def w_is_compiled(vm: "SPyVM") -> W_Bool:
    return B.w_False
