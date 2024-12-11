from typing import TYPE_CHECKING, Sequence, Optional
from dataclasses import dataclass
import textwrap
from spy.fqn import FQN
from spy.location import Loc
from spy.vm.object import W_Object
from spy.vm.function import W_Func, W_FuncType, W_DirectCall
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

# simulate Algebraic Data Type
class ArgSpec:
    pass

@dataclass
class Arg(ArgSpec):
    i: int
    w_converter: Optional[W_Func] = None

@dataclass
class Const(ArgSpec):
    w_const: W_Object
    loc: Loc

ArgSpec.Arg = Arg      # type: ignore
ArgSpec.Const = Const  # type: ignore

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
        sig = self.w_functype.signature
        fqn = self.w_func.fqn
        return f'<spy adapter `{sig}` for `{fqn}`>'

    def is_direct_call(self) -> bool:
        """
        This is a hack. See W_Func.op_CALL and ASTFrame.eval_expr_Call.
        """
        return isinstance(self.w_func, W_DirectCall)

    def raw_call(self, vm: 'SPyVM', args_w: Sequence[W_Object]) -> W_Object:
        # hack hack hack, we should kill all of this eventually
        if self.is_direct_call():
            w_func = args_w[0]
            assert isinstance(w_func, W_Func)
        else:
            w_func = self.w_func

        def getarg(spec: ArgSpec) -> W_Object:
            if isinstance(spec, Arg):
                w_arg = args_w[spec.i]
                if spec.w_converter:
                    w_arg = vm.fast_call(spec.w_converter, [w_arg])
                return w_arg
            elif isinstance(spec, Const):
                return spec.w_const
            else:
                assert False

        real_args_w = [getarg(spec) for spec in self.args]
        return vm.fast_call(w_func, real_args_w)

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
