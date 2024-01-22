from typing import Callable
from dataclasses import dataclass
from spy.fqn import FQN
from spy.vm.function import W_FuncType, W_BuiltinFunc

@dataclass
class RegisteredFunction:
    fqn: FQN
    w_functype: W_FuncType
    pyfunc: Callable

FUNCTIONS = []

def register_function(fqn, sig):
    w_functype = W_FuncType.parse(sig)
    def decorator(pyfunc):
        FUNCTIONS.append(
            RegisteredFunction(fqn, w_functype, pyfunc)
        )
        return pyfunc
    return decorator
