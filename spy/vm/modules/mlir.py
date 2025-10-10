from typing import TYPE_CHECKING

from spy.vm.object import W_Type
from spy.vm.primitive import W_Str
from spy.vm.registry import ModuleRegistry

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

MLIR = ModuleRegistry("mlir")


@MLIR.builtin_func(color="blue", kind="generic")
def w_Type(vm: "SPyVM", w_s: Str) -> W_Type:
    breakpoint()
