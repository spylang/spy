import textwrap
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Optional, Sequence

from spy.fqn import FQN
from spy.location import Loc
from spy.vm.b import OPERATOR, B
from spy.vm.function import W_Func, W_FuncType
from spy.vm.object import W_Object

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


# simulate Algebraic Data Type
class ArgSpec:
    Arg: ClassVar[type["Arg"]]
    Const: ClassVar[type["Const"]]
    Convert: ClassVar[type["Convert"]]


@dataclass
class Arg(ArgSpec):
    i: int


@dataclass
class Const(ArgSpec):
    w_const: W_Object
    loc: Loc


@dataclass
class Convert(ArgSpec):
    # Convert the arg by calling the given opimpl.
    # Note that with this we are effectively builting a tree of opimpls.
    w_conv_opimpl: "W_OpImpl"
    expT: ArgSpec
    gotT: ArgSpec
    arg: ArgSpec


ArgSpec.Arg = Arg  # type: ignore
ArgSpec.Const = Const  # type: ignore
ArgSpec.Convert = Convert  # type: ignore


@OPERATOR.builtin_type("OpImpl")
class W_OpImpl(W_Object):
    """
    The typechecked counterpart of OpSpec.

    OpSpec specifies how an operation must be done, e.g. "call this function
    with these two arguments".

    typechecker.typecheck() transforms an OpSpec into an OpImpl, which is
    ready to be executed. In particular, OpImpl contains all the conversions
    which might be necessary to perform, in case the signature of the function
    doesn't match the type of the MetaArgs.

    OpImpl is not a function, but behaves like one: it expects a certain
    number of positional arguments with certain types, and it has a return
    type and a color. For simplicity, we use `w_functype` for this purpose,
    but it's important to understand that it's not a function (in particular,
    it cannot be called by normal means).

    When execute()d, W_OpImpl transforms the input args_w into the "real"
    args_w which is passed to w_func.

    The transformation rules are stored into a list of ArgSpec, which
    effectively encodes a mini-AST.
    """

    # This is a mess, because we can either represent a function call or a
    # single constant. Eventually, we need to turn it into a real AST.
    #
    # Invariants:
    #   - w_functype is always present
    #   - either _w_func or _w_const is present
    #   - _args is present only if _w_func is present
    w_functype: W_FuncType
    _w_func: Optional[W_Func]
    _args: Optional[list[ArgSpec]]
    _w_const: Optional[W_Object]

    def __init__(
        self,
        w_functype: W_FuncType,
        w_func: Optional[W_Func],
        args: Optional[list[ArgSpec]],
    ) -> None:
        self.w_functype = w_functype
        self._w_func = w_func
        self._args = args
        self._w_const = None

    @staticmethod
    def const(vm: "SPyVM", w_const: W_Object) -> "W_OpImpl":
        w_T = vm.dynamic_type(w_const)
        w_functype = W_FuncType.new([], w_T, color="blue")
        w_opimpl = W_OpImpl(w_functype, None, None)
        w_opimpl._w_const = w_const
        return w_opimpl

    def is_func_call(self) -> bool:
        if self._w_func is not None:
            assert self._args is not None
            return True
        return False

    def is_const(self) -> bool:
        return self._w_const is not None

    @property
    def w_func(self) -> W_Func:
        assert self._w_func is not None
        return self._w_func

    @property
    def args(self) -> list[ArgSpec]:
        assert self._args is not None
        return self._args

    @property
    def w_const(self) -> W_Object:
        assert self._w_const is not None
        return self._w_const

    def __repr__(self) -> str:
        if self.is_const():
            return f"<OpImpl const {self.w_const}>"
        else:
            assert self.is_func_call()
            sig = self.w_functype.fqn.human_name
            fqn = self.w_func.fqn
            return f"<OpImpl `{sig}` for `{fqn}`>"

    def is_pure(self) -> bool:
        return self.is_const() or self.w_func.is_pure()

    def _execute(self, vm: "SPyVM", args_w: Sequence[W_Object]) -> W_Object:
        if self.is_const():
            return self.w_const

        def getarg(spec: ArgSpec) -> W_Object:
            if isinstance(spec, Arg):
                return args_w[spec.i]
            elif isinstance(spec, Const):
                return spec.w_const
            elif isinstance(spec, Convert):
                w_expT = getarg(spec.expT)
                w_gotT = getarg(spec.gotT)
                w_arg = getarg(spec.arg)
                return spec.w_conv_opimpl._execute(vm, [w_expT, w_gotT, w_arg])
            else:
                assert False

        real_args_w = [getarg(spec) for spec in self.args]
        return vm.fast_call(self.w_func, real_args_w)

    def pp(self) -> None:
        print(self.render())

    def render(self) -> str:
        """
        Return a human-readable representation of the OpImpl
        """
        argnames = [f"v{i}" for i, p in enumerate(self.w_functype.params)]

        def fmt_opimpl_call(opimpl: "W_OpImpl", arg_reprs: list[str]) -> str:
            """
            Recursively render an opimpl call with given argument representations
            """

            def fmt_spec(spec: ArgSpec) -> str:
                if isinstance(spec, Arg):
                    return arg_reprs[spec.i]
                elif isinstance(spec, Const):
                    return str(spec.w_const)
                elif isinstance(spec, Convert):
                    converter_arg_reprs = [
                        fmt_spec(spec.expT),
                        fmt_spec(spec.gotT),
                        fmt_spec(spec.arg),
                    ]
                    return fmt_opimpl_call(spec.w_conv_opimpl, converter_arg_reprs)
                else:
                    assert False

            args = [fmt_spec(s) for s in opimpl.args]
            arglist = ", ".join(args)
            return f"`{opimpl.w_func.fqn}`({arglist})"

        sig = self.func_signature()
        body = fmt_opimpl_call(self, argnames)
        return textwrap.dedent(f"""
        {sig}:
            return {body}
        """).strip()

    def func_signature(self) -> str:
        w_ft = self.w_functype
        params = [f"v{i}: {p.w_T.fqn.human_name}" for i, p in enumerate(w_ft.params)]
        str_params = ", ".join(params)
        resname = w_ft.w_restype.fqn.human_name
        s = f"def({str_params}) -> {resname}"
        return s
