"""
Second half of the `builtins` module.

The first half is in vm/b.py. See its docstring for more details.
"""

from typing import TYPE_CHECKING
from spy.vm.object import W_I32
from spy.vm.b import BUILTINS
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@BUILTINS.primitive('def(x: i32) -> i32')
def abs(vm: 'SPyVM', w_x: W_I32) -> W_I32:
    x = vm.unwrap_i32(w_x)
    res = vm.ll.call('spy_builtins__abs', x)
    return vm.wrap(res) # type: ignore
