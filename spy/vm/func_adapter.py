from typing import TYPE_CHECKING, Sequence, Optional, ClassVar
from dataclasses import dataclass
import textwrap
from spy.fqn import FQN
from spy.location import Loc
from spy.vm.object import W_Object
from spy.vm.function import W_Func, W_FuncType
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

# simulate Algebraic Data Type
class ArgSpec:
    Arg: ClassVar[type['Arg']]
    Const: ClassVar[type['Const']]
    Convert: ClassVar[type['Convert']]

@dataclass
class Arg(ArgSpec):
    i: int

@dataclass
class Const(ArgSpec):
    w_const: W_Object
    loc: Loc

@dataclass
class Convert(ArgSpec):
    w_conv: W_Func
    arg: ArgSpec

ArgSpec.Arg = Arg          # type: ignore
ArgSpec.Const = Const      # type: ignore
ArgSpec.Convert = Convert  # type: ignore

class W_FuncAdapter(W_Func):
    """
    Adapt another w_func to a different signature.

    When called, W_FuncAdapter transforms the input args_w into the "real"
    args_w which is passed to w_func.

    The transformation rules are stored into a list of ArgSpec, which
    effectively encodes a mini-AST.
    """
    fqn = FQN('builtins::__adapter__')

    def __init__(self, w_functype: W_FuncType, w_func: W_Func,
                 args: list[ArgSpec]) -> None:
        self.w_functype = w_functype
        self.w_func = w_func
        self.args = args

    def __repr__(self) -> str:
        sig = self.w_functype.fqn.human_name
        fqn = self.w_func.fqn
        return f'<spy adapter `{sig}` for `{fqn}`>'

    def is_pure(self) -> bool:
        return self.w_func.is_pure()

    def raw_call(self, vm: 'SPyVM', args_w: Sequence[W_Object]) -> W_Object:
        def getarg(spec: ArgSpec) -> W_Object:
            if isinstance(spec, Arg):
                return args_w[spec.i]
            elif isinstance(spec, Const):
                return spec.w_const
            elif isinstance(spec, Convert):
                w_arg = getarg(spec.arg)
                return vm.fast_call(spec.w_conv, [w_arg])
            else:
                assert False

        real_args_w = [getarg(spec) for spec in self.args]
        return vm.fast_call(self.w_func, real_args_w)

    def pp(self) -> None:
        print(self.render())

    def render(self) -> str:
        """
        Return a human-readable representation of the adapter
        """
        argnames = [p.name for p in self.w_functype.params]
        def fmt(spec: ArgSpec) -> str:
            if isinstance(spec, Arg):
                arg = argnames[spec.i]
                return arg
            elif isinstance(spec, Const):
                return str(spec.w_const)
            elif isinstance(spec, Convert):
                fqn = spec.w_conv.fqn
                arg = fmt(spec.arg)
                return f'`{fqn}`({arg})'
            else:
                assert False

        sig = self.func_signature()
        args = [fmt(spec) for spec in self.args]
        arglist = ', '.join(args)
        return textwrap.dedent(f"""
        {sig}:
            return `{self.w_func.fqn}`({arglist})
        """).strip()

    def func_signature(self) -> str:
        w_ft = self.w_functype
        params = [f'{p.name}: {p.w_type.fqn.human_name}' for p in w_ft.params]
        str_params = ', '.join(params)
        resname = w_ft.w_restype.fqn.human_name
        s = f'def({str_params}) -> {resname}'
        return s
