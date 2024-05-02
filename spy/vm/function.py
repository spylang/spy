from dataclasses import dataclass
import inspect
from typing import TYPE_CHECKING, Any, Optional, Callable
from spy import ast
from spy.ast import Color
from spy.fqn import QN, FQN
from spy.vm.object import W_Object, W_Type, W_Dynamic, w_DynamicType
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

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
        sig = self._str_sig()
        super().__init__(f'def{sig}', W_Func)

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

    def _str_sig(self) -> str:
        params = [f'{p.name}: {p.w_type.name}' for p in self.params]
        str_params = ', '.join(params)
        resname = self.w_restype.name
        return f'({str_params}) -> {resname}'



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

    def spy_call(self, vm: 'SPyVM', args_w: list[W_Object]) -> W_Object:
        """
        Call the function.

        args_w contains the list of wrapped arguments. Note that here we
        assume that they are of the correct type: end users should use
        vm.call_function, which is the official API and does typecheck.
        """
        raise NotImplementedError


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

    def spy_call(self, vm: 'SPyVM', args_w: list[W_Object]) -> W_Object:
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
        self.pyfunc = pyfunc

    def __repr__(self) -> str:
        return f"<spy function '{self.qn}' (builtin)>"

    def spy_call(self, vm: 'SPyVM', args_w: list[W_Object]) -> W_Object:
        return self.pyfunc(vm, *args_w)


def spy_builtin(qn: QN) -> Callable:
    """
    Decorator to make an interp-level function wrappable by the VM.

    Example of usage:

        @spy_builtin(QN("foo::hello"))
        def hello(vm: 'SPyVM', w_x: W_I32) -> W_Str:
            ...

        w_hello = vm.wrap(hello)
        assert isinstance(w_hello, W_BuiltinFunc)
        assert w_hello.qn == QN("foo::hello")

    The w_functype of the wrapped function is automatically computed by
    inspectng the signature of the interp-level function. The first parameter
    MUST be 'vm'.
    """
    # this is B.w_dynamic (we cannot use B due to circular imports)
    B_w_dynamic = w_DynamicType

    def is_W_class(x: Any) -> bool:
        return isinstance(x, type) and issubclass(x, W_Object)

    def to_spy_FuncParam(p: Any) -> FuncParam:
        if p.name.startswith('w_'):
            name = p.name[2:]
        else:
            name = p.name
        #
        pyclass = p.annotation
        if pyclass is W_Dynamic:
            return FuncParam(name, B_w_dynamic)
        elif issubclass(pyclass, W_Object):
            return FuncParam(name, pyclass._w)
        else:
            raise ValueError(f"Invalid param: '{p}'")

    def decorator(fn: Callable) -> Callable:
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())
        if len(params) == 0:
            msg = (f"The first param should be 'vm: SPyVM'. Got nothing")
            raise ValueError(msg)
        if (params[0].name != 'vm' or
            params[0].annotation != 'SPyVM'):
            msg = (f"The first param should be 'vm: SPyVM'. Got '{params[0]}'")
            raise ValueError(msg)

        func_params = [to_spy_FuncParam(p) for p in params[1:]]
        ret = sig.return_annotation
        if ret is W_Dynamic:
            w_restype = B_w_dynamic
        elif is_W_class(ret):
            w_restype = ret._w
        else:
            raise ValueError(f"Invalid return type: '{sig.return_annotation}'")

        w_functype = W_FuncType(func_params, w_restype)
        fn._w = W_BuiltinFunc(w_functype, qn, fn)  # type: ignore
        fn.w_functype = w_functype  # type: ignore
        return fn

    return decorator
