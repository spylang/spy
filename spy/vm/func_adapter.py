from typing import TYPE_CHECKING, Sequence
from dataclasses import dataclass
import textwrap
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
    w_converter: W_Func = None

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
        def getarg(spec):
            if isinstance(spec, Arg):
                w_arg = args_w[spec.i]
                if spec.w_converter:
                    w_arg = spec.w_converter.spy_call(vm, [w_arg])
                return w_arg
            elif isinstance(spec, Const):
                return spec.w_const
            else:
                assert False

        real_args_w = [getarg(spec) for spec in self.args]
        return self.w_func.spy_call(vm, real_args_w)

    def pp(self):
        print(self.render())

    def render(self):
        """
        Return a human-readable representation of the adapter
        """
        argnames = [p.name for p in self.w_functype.params]
        def fmt(spec):
            if isinstance(spec, Arg):
                arg = argnames[spec.i]
                if spec.w_converter:
                    fqn = spec.w_converter.fqn
                    return f'`{fqn}`({arg})'
                return arg
            elif isinstance(spec, Const):
                return str(spec.w_const)
            else:
                assert False

        args = [fmt(spec) for spec in self.args]
        arglist = ', '.join(args)
        return textwrap.dedent(f"""
        {self.w_functype.signature}:
            return `{self.w_func.fqn}`({arglist})
        """).strip()
