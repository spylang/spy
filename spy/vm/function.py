from dataclasses import dataclass
from typing import (TYPE_CHECKING, Any, Optional, Callable, Sequence, Literal,
                    Iterator)
from spy import ast
from spy.location import Loc
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

    @staticmethod
    def op_EQ(vm: 'SPyVM', wop_l: 'W_OpArg', wop_r: 'W_OpArg') -> 'W_OpImpl':
        from spy.vm.opimpl import W_OpImpl
        from spy.vm.modules.builtins import w_functype_eq
        if wop_l.w_static_type is wop_r.w_static_type:
            return W_OpImpl(w_functype_eq)
        else:
            return W_OpImpl.NULL

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
    def is_varargs(self) -> bool:
        return bool(self.params) and self.params[-1].kind == 'varargs'

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

    def is_argcount_ok(self, n: int) -> bool:
        if self.is_varargs:
            return n >= self.arity
        else:
            return n == self.arity

    def all_params(self) -> Iterator[FuncParam]:
        """
        Iterate over all params. Go to infinity in case of varargs
        """
        if self.is_varargs:
            for param in self.params[:-1]:
                yield param
            last_param = self.params[-1]
            while True:
                yield last_param
        else:
            for param in self.params:
                yield param

# we cannot use @builtin_type because of circular import issues. Let's build
# the app-level type manually
W_FuncType._w = W_Type(FQN('builtins::functype'), W_FuncType)


class W_Func(W_Object):
    __spy_storage_category__ = 'reference'

    w_functype: W_FuncType
    fqn: FQN
    def_loc: Loc

    @property
    def color(self) -> Color:
        """
        Just a shortcut
        """
        return self.w_functype.color

    def is_pure(self) -> bool:
        """
        The result of pure functions depend only on their argument,
        without side effects.

        This means that if we call a red pure function with blue arguments,
        the result can be blue.

        Maybe the proper thing to do is to introduce a new color and store
        this info on the w_functype.
        """
        # this is a hack, but good enough to constant-fold arithmetic ops
        return self.fqn.modname == 'operator'

    def spy_get_w_type(self, vm: 'SPyVM') -> W_Type:
        return self.w_functype

    def raw_call(self, vm: 'SPyVM', args_w: Sequence[W_Object]) -> W_Object:
        """
        Call the function.

        This is the simplest calling convention, and it's at the base to
        everything else. Arguments can be passed ONLY positionally, and they
        must be of the correct type, no conversions are allowed here.

        Also, raw_call bypasses the blue cache.

        You should never call this directly. Use vm.call or vm.fast_call.
        """
        raise NotImplementedError

    @staticmethod
    def op_CALL(vm: 'SPyVM', wop_func: 'W_OpArg',
                *args_wop: 'W_OpArg') -> 'W_OpImpl':
        from spy.vm.opimpl import W_OpImpl
        w_func = wop_func.w_blueval
        assert isinstance(w_func, W_Func)
        return W_OpImpl(
            w_func,
            list(args_wop),
            is_direct_call = True,
        )


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
        self.def_loc = funcdef.prototype_loc
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

    def raw_call(self, vm: 'SPyVM', args_w: Sequence[W_Object]) -> W_Object:
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
        self.def_loc = Loc.from_pyfunc(pyfunc)
        # _pyfunc should NEVER be called directly, because it bypasses the
        # bluecache
        self._pyfunc = pyfunc

    def __repr__(self) -> str:
        return f"<spy function '{self.fqn}' (builtin)>"

    def raw_call(self, vm: 'SPyVM', args_w: Sequence[W_Object]) -> W_Object:
        from spy.vm.b import B
        w_res = self._pyfunc(vm, *args_w)
        if w_res is None and self.w_functype.w_restype is B.w_void:
            return vm.wrap(None)
        return w_res
