"""
Additional builtins.

This is a bit ugly but it has to be separated from builtins.py to avoid
circular imports
"""

from typing import Optional
from spy.fqn import FQN
from spy.vm.function import W_BuiltinFunc
from spy.vm import ops

class B2:
    w_abs = W_BuiltinFunc(ops.abs.w_functype, FQN('builtins::abs'), ops.abs)
