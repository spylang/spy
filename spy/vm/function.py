from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Callable, Sequence, Literal
from spy import ast
from spy.ast import Color
from spy.fqn import FQN, NSPart
from spy.vm.object import W_Object, W_Type
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.opimpl import W_OpImpl, W_OpArg

# dictionary which contains local vars in an ASTFrame. The type is defined
# here because it's also used by W_ASTFunc.closure.
Namespace = dict[str, Optional[W_Object]]

FuncParamKind = Literal['simple', 'varargs']

@dataclass(frozen=True, eq=True)
class FuncParam:
    name: str
    w_type: W_Type
    kind: FuncParamKind


@dataclass(repr=False, eq=True)
class W_FuncType(W_Type):
    color: Color
    params: list[FuncParam]
    w_restype: W_Type

    def __init__(self, params: list[FuncParam], w_restype: W_Type,
                 *, color: Color = 'red') -> None:
        # sanity check
        if params:
            assert isinstance(params[0], FuncParam)
        self.params = params
        self.w_restype = w_restype
        self.color = color
        #
        # build an artificial FQN for the functype.
        # For 'def(i32, i32) -> bool', the FQN looks like this:
        #    builtins::def[i32, i32, bool]
        #
        # XXX the FQN is not necessarily unique, we don't take into account
        # param names
        qualifiers = [p.w_type.fqn for p in self.params] + [w_restype.fqn]
        fqn = FQN('builtins').join('def', qualifiers)
        super().__init__(fqn, W_Func)

    @property
    def signature(self) -> str:
        params = [f'{p.name}: {p.w_type.fqn.human_name}' for p in self.params]
        str_params = ', '.join(params)
        resname = self.w_restype.fqn.human_name
        s = f'def({str_params}) -> {resname}'
        if self.color == 'blue':
            s = f'@blue {s}'
        return s

    def __repr__(self) -> str:
        return f"<spy type '{self.signature}'>"

    def __hash__(self) -> int:
        return hash((self.fqn, self.color, tuple(self.params), self.w_restype))

    @classmethod
    def make(cls,
             *,
             w_restype: W_Type,
             color: Color = 'red',
             **kwargs: W_Type
             ) -> 'W_FuncType':
        """
        Small helper to make it easier to build W_FuncType, especially in
        tests
        """
        params = [FuncParam(key, w_type, 'simple')
                  for key, w_type in kwargs.items()]
        return cls(params, w_restype, color=color)

    @classmethod
    def parse(cls, s: str) -> 'W_FuncType':
        """
        Quick & dirty function to parse function types.

        It's meant to be used in tests, it's not robust at all, especially in
        case of wrong inputs.
        """
        from spy.vm.b import B

        def parse_type(s: str) -> Any:
            attr = f'w_{s}'
            if hasattr(B, attr):
                return getattr(B, attr)
            assert False, f'Cannot find type {s}'

        args, res = map(str.strip, s.split('->'))
        assert args.startswith('def(')
        assert args.endswith(')')
        kwargs = {}
        arglist = args[4:-1].split(',')
        for arg in arglist:
            if arg == '':
                continue
            argname, argtype = map(str.strip, arg.split(':'))
            kwargs[argname] = parse_type(argtype)
        #
        w_restype = parse_type(res)
        return cls.make(w_restype=w_restype, **kwargs)

    @property
    def arity(self) -> int:
        """
        Return the *minimum* number of arguments expected by the function.
        In case of varargs, it's the number of non-varargs paramenters.
        """
        if self.is_varargs:
            return len(self.params) - 1
        else:
            return len(self.params)

    @property
    def is_varargs(self) -> bool:
        return bool(self.params) and self.params[-1].kind == 'varargs'



class W_Func(W_Object):
    w_functype: W_FuncType
    fqn: FQN

    @property
    def color(self) -> Color:
        """
        Just a shortcut
        """
        return self.w_functype.color

    def spy_get_w_type(self, vm: 'SPyVM') -> W_Type:
        return self.w_functype

    def spy_call(self, vm: 'SPyVM', args_w: Sequence[W_Object]) -> W_Object:
        """
        Call the function.

        args_w contains the list of wrapped arguments. Note that here we
        assume that they are of the correct type: end users should use
        vm.call_function, which is the official API and does typecheck.
        """
        raise NotImplementedError

    @staticmethod
    def op_CALL(vm: 'SPyVM', wop_func: 'W_OpArg',
                *args_wop: 'W_OpArg') -> 'W_OpImpl':
        """
        This is a bit of a hack.

        The correct opimpl for a W_Func object is something which says "please
        just call it". Ideally, we would like to do something like that:

            w_func = wop_func.blue_unwrap()
            return W_OpImpl(w_func, ...)

        However, we cannot because at the current moment, wop_func doesn't
        carry around it's blue value: this is something which needs to be
        fixed in the typechecker, eventually.

        The workaround is to wrap the functype inside a special W_DirectCall
        object, which is special cased by ASTFrame.
        """
        from spy.vm.opimpl import W_OpImpl
        w_functype = wop_func.w_static_type
        assert isinstance(w_functype, W_FuncType)
        return W_OpImpl(
            W_DirectCall(w_functype),
            list(args_wop),
        )


class W_DirectCall(W_Func):
    """
    See W_Func.op_CALL.
    """
    fqn = FQN("builtins::__direct_call__")

    def __init__(self, w_functype: W_FuncType) -> None:
        self.w_functype = w_functype

    def __repr__(self) -> str:
        return f'W_DirectCall({self.w_functype})'


class W_ASTFunc(W_Func):
    funcdef: ast.FuncDef
    closure: tuple[Namespace, ...]
    # types of local variables: this is non-None IIF the function has been
    # redshifted.
    locals_types_w: Optional[dict[str, W_Type]]

    def __init__(self,
                 w_functype: W_FuncType,
                 fqn: FQN,
                 funcdef: ast.FuncDef,
                 closure: tuple[Namespace, ...],
                 *,
                 locals_types_w: Optional[dict[str, W_Type]] = None
                 ) -> None:
        self.w_functype = w_functype
        self.fqn = fqn
        self.funcdef = funcdef
        self.closure = closure
        self.locals_types_w = locals_types_w

    @property
    def redshifted(self) -> bool:
        return self.locals_types_w is not None

    def __repr__(self) -> str:
        if self.redshifted:
            extra = ' (redshifted)'
        elif self.color == 'blue':
            extra = ' (blue)'
        else:
            extra = ''
        return f"<spy function '{self.fqn}'{extra}>"

    def spy_call(self, vm: 'SPyVM', args_w: Sequence[W_Object]) -> W_Object:
        from spy.vm.astframe import ASTFrame
        frame = ASTFrame(vm, self)
        return frame.run(args_w)


class W_BuiltinFunc(W_Func):
    """
    Builtin functions are implemented by calling an interp-level function
    (written in Python).
    """
    pyfunc: Callable

    def __init__(self, w_functype: W_FuncType, fqn: FQN,
                 pyfunc: Callable) -> None:
        self.w_functype = w_functype
        self.fqn = fqn
        # _pyfunc should NEVER be called directly, because it bypasses the
        # bluecache
        self._pyfunc = pyfunc

    def __repr__(self) -> str:
        return f"<spy function '{self.fqn}' (builtin)>"

    def spy_call(self, vm: 'SPyVM', args_w: Sequence[W_Object]) -> W_Object:
        from spy.vm.b import B
        w_res = self._pyfunc(vm, *args_w)
        if w_res is None and self.w_functype.w_restype is B.w_void:
            return vm.wrap(None)
        return w_res
