from typing import TYPE_CHECKING

from spy.vm.registry import ModuleRegistry
from spy.vm.str import W_Str

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

MODULE = ModuleRegistry("mymod")


@MODULE.builtin_func
def w_get_name(vm: "SPyVM") -> W_Str:
    return vm.wrap("hello from mymod")
