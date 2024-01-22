"""
Additional builtins.

This is a bit ugly but it has to be separated from builtins.py to avoid
circular imports
"""

from typing import Optional
from spy.fqn import FQN
from spy.vm.function import W_BuiltinFunc
from spy.vm.registry import register_function
from spy.vm.object import W_i32


@register_function(FQN('builtins::abs'), 'def(x: i32) -> i32')
def abs(vm: 'SPyVM', w_x: W_i32) -> W_i32:
    x = vm.unwrap_i32(w_x)
    res = vm.ll.call('spy_builtins__abs', x)
    return vm.wrap(res) # type: ignore
