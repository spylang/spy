from typing import TYPE_CHECKING, Sequence
from dataclasses import dataclass
from spy.fqn import FQN
from spy.vm.object import W_Object
from spy.vm.function import W_Func, W_FuncType
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

# simulate Algebraic Data Type
class ArgSpec:
    pass

@dataclass
class Arg(ArgSpec):
    i: int

@dataclass
class Const(ArgSpec):
    w_const: W_Object

ArgSpec.Arg = Arg
ArgSpec.Const = Const

class W_FuncAdapter(W_Func):
    """
    WRITE ME
    """
    fqn = FQN('builtins::__adapter__')


    def __init__(self, w_functype: W_FuncType, w_func: W_Func,
                 args: list[ArgSpec]) -> None:
        self.w_functype = w_functype
        self.w_func = w_func
        self.args = args

    def spy_call(self, vm: 'SPyVM', args_w: Sequence[W_Object]) -> W_Object:
        real_args_w = []
        for spec in self.args:
            if isinstance(spec, Arg):
                real_args_w.append(args_w[spec.i])
            elif isinstance(spec, Const):
                real_args_w.append(spec.w_const)
            else:
                assert False
        return self.w_func.spy_call(vm, real_args_w)
