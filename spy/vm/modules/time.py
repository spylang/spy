"""
SPy `time` module.
"""
from typing import TYPE_CHECKING
from spy.vm.primitive import W_F64
from spy.vm.registry import ModuleRegistry
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

TIME = ModuleRegistry("time")

@TIME.builtin_func
def w_time(vm: "SPyVM") -> W_F64:
    import time
    return W_F64(time.time())

@TIME.builtin_func
def w_sleep(vm: "SPyVM", w_seconds: W_F64) -> None:
    import time
    time.sleep(w_seconds.value)
