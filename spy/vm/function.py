from dataclasses import dataclass
from typing import (TYPE_CHECKING, Any, Optional, Callable, Sequence, Literal,
                    Iterator, Self)
from spy import ast
from spy.location import Loc
from spy.ast import Color, FuncKind
from spy.fqn import FQN
from spy.vm.object import W_Object, W_Type, builtin_method
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.opspec import W_OpSpec, W_OpArg

# dictionary which contains local vars in an ASTFrame. The type is defined
# here because it's also used by W_ASTFunc.closure.
Namespace = dict[str, Optional[W_Object]]
CLOSURE = tuple[Namespace, ...]

FuncParamKind = Literal['simple', 'varargs']

@dataclass(frozen=True, eq=True)
class FuncParam:
    w_T: W_Type
    kind: FuncParamKind


@dataclass(repr=False, eq=True)
class W_FuncType(W_Type):
    color: Color
    kind: FuncKind
    params: list[FuncParam]
    w_restype: W_Type

    @classmethod
    def new(cls, params: list[FuncParam], w_restype: W_Type,
            *, color: Color = 'red', kind: FuncKind = 'plain') -> 'Self':
        # build an artificial FQN for the functype.
        # E.g. for 'def(i32, i32) -> bool', the FQN looks like this:
        #    builtins::def[i32, i32, bool]
        qualifiers = [p.w_T.fqn for p in params] + [w_restype.fqn]
        if color == 'red' and kind == 'plain':
            t = 'def'
        elif color == 'blue' and kind == 'plain':
            t = 'blue.def'
        elif color == 'blue' and kind == 'generic':
            t = 'blue.generic.def'
        elif color == 'blue' and kind == 'metafunc':
            t = 'blue.metafunc.def'
        else:
            assert False
        fqn = FQN('builtins').join(t, qualifiers)

        w_functype = super().from_pyclass(fqn, W_Func)
        w_functype.params = params
        w_functype.w_restype = w_restype
        w_functype.color = color
        w_functype.kind = kind
        return w_functype

    def __hash__(self) -> int:
        return hash((self.fqn, self.color, tuple(self.params), self.w_restype))

    @builtin_method('__eq__', color='blue', kind='metafunc')
    @staticmethod
    def w_EQ(vm: 'SPyVM', wop_l: 'W_OpArg', wop_r: 'W_OpArg') -> 'W_OpSpec':
        from spy.vm.opspec import W_OpSpec
        from spy.vm.modules.builtins import w_functype_eq
        if wop_l.w_static_T is wop_r.w_static_T:
            return W_OpSpec(w_functype_eq)
        else:
            return W_OpSpec.NULL

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
        params = []
        arglist = args[4:-1].split(',')
        for argtype in arglist:
            if argtype == '':
                continue
            w_T = parse_type(argtype.strip())
            params.append(FuncParam(w_T, 'simple'))
        #
        w_restype = parse_type(res)
        if w_restype is B.w_None:
            # special case None and allow to use it as a type even if it's not
            w_restype = B.w_NoneType
        return cls.new(params, w_restype)

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
W_FuncType._w = W_Type.declare(FQN('builtins::functype'))

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
        return (self.fqn.modname == 'operator'
                and self.fqn.symbol_name != 'raise')

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

    # NOTE: we cannot use applevel '__call__' or '__getitem__' here, for
    # bootstrapping reason.
    # These operators are special cased by
    # callop.w_CALL and itemop.w_GETITEM, depending on whether w_functype.kind
    # is 'plain' or 'generic'.
    @staticmethod
    def op_CALL(vm: 'SPyVM', wop_func: 'W_OpArg',
                *args_wop: 'W_OpArg') -> 'W_OpSpec':
        from spy.vm.opspec import W_OpSpec
        w_func = wop_func.w_blueval
        assert isinstance(w_func, W_Func)

        if w_func.w_functype.kind == 'metafunc':
            # call the metafunc to get the opspec
            w_opspec = vm.fast_call(w_func, list(args_wop))
            assert isinstance(w_opspec, W_OpSpec)
            return w_opspec
        else:
            # return the func as the opspec
            return W_OpSpec(
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
        frame = ASTFrame(vm, self, args_w)
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
        if w_res is None and self.w_functype.w_restype is B.w_NoneType:
            return vm.wrap(None)
        return w_res
