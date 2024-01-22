"""
Additional builtins.

This is a bit ugly but it has to be separated from builtins.py to avoid
circular imports
"""

from typing import TYPE_CHECKING
from spy.vm.registry import ModuleRegistry
from spy.vm.object import W_i32
from spy.vm.builtins import B

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@B.primitive('def(x: i32) -> i32')
def abs(vm: 'SPyVM', w_x: W_i32) -> W_i32:
    x = vm.unwrap_i32(w_x)
    res = vm.ll.call('spy_builtins__abs', x)
    return vm.wrap(res) # type: ignore
