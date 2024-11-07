from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Callable, Sequence
from spy import ast
from spy.ast import Color
from spy.fqn import QN, NSPart
from spy.vm.primitive import W_Void
from spy.vm.object import W_Object, W_Type
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.list import W_List
    from spy.vm.opimpl import W_OpImpl, W_OpArg

# dictionary which contains local vars in an ASTFrame. The type is defined
# here because it's also used by W_ASTFunc.closure.
Namespace = dict[str, Optional[W_Object]]


@dataclass
class FuncParam:
    name: str
    w_type: W_Type


@dataclass(repr=False)
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
        # build an artificial QN for the functype. Note that the QN is not
        # necessarily unique (e.g., we don't take into account param names),
        # but that's ok because it will be uniquified when it becomes an FQN.
        # The QN looks like:
        #    builtins::def[args[i32, i32], bool]
        def T(w_type: W_Type) -> NSPart:
            "Convert a W_Type into an NSPart"
            return NSPart(w_type.qn.symbol_name, [])

        args = NSPart('args', [T(p.w_type) for p in self.params])
        ret = T(w_restype)
        qn = QN(['builtins', NSPart('def', [args, ret])])
        super().__init__(qn, W_Func)

    @property
    def signature(self) -> str:
        params = [f'{p.name}: {p.w_type.qn.human_name}' for p in self.params]
        str_params = ', '.join(params)
        resname = self.w_restype.qn.human_name
        s = f'def({str_params}) -> {resname}'
        if self.color == 'blue':
            s = f'@blue {s}'
        return s

    def __repr__(self) -> str:
        return f"<spy type '{self.signature}'>"

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
        params = [FuncParam(key, w_type) for key, w_type in kwargs.items()]
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
        return len(self.params)



class W_Func(W_Object):
    w_functype: W_FuncType
    qn: QN

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
                w_opargs: 'W_List[W_OpArg]') -> 'W_OpImpl':
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
            w_opargs.items_w           # type: ignore
        )


class W_DirectCall(W_Func):
    """
    See W_Func.op_CALL.
    """
    qn = QN("builtins::__direct_call__")

    def __init__(self, w_functype: W_FuncType) -> None:
        self.w_functype = w_functype


class W_ASTFunc(W_Func):
    funcdef: ast.FuncDef
    closure: tuple[Namespace, ...]
    # types of local variables: this is non-None IIF the function has been
    # redshifted.
    locals_types_w: Optional[dict[str, W_Type]]

    def __init__(self,
                 w_functype: W_FuncType,
                 qn: QN,
                 funcdef: ast.FuncDef,
                 closure: tuple[Namespace, ...],
                 *,
                 locals_types_w: Optional[dict[str, W_Type]] = None
                 ) -> None:
        self.w_functype = w_functype
        self.qn = qn
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
        return f"<spy function '{self.qn}'{extra}>"

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

    def __init__(self, w_functype: W_FuncType, qn: QN,
                 pyfunc: Callable) -> None:
        self.w_functype = w_functype
        self.qn = qn
        # _pyfunc should NEVER be called directly, because it bypasses the
        # bluecache
        self._pyfunc = pyfunc

    def __repr__(self) -> str:
        return f"<spy function '{self.qn}' (builtin)>"

    def spy_call(self, vm: 'SPyVM', args_w: Sequence[W_Object]) -> W_Object:
        # we cannot import B due to circular imports, let's fake it
        B_w_Void = W_Void._w
        w_res = self._pyfunc(vm, *args_w)
        if w_res is None and self.w_functype.w_restype is B_w_Void:
            return vm.wrap(None)
        return w_res
