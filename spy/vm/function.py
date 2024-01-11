from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional
from spy import ast
from spy.ast import Color
from spy.fqn import FQN
from spy.vm.object import W_Object, W_Type, W_i32
from spy.vm.module import W_Module
from spy.vm.varstorage import VarStorage
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
        case of wrong inputs. It supports only builtin types.
        """
        from spy.vm.builtins import B
        def parse_type(s: str) -> Any:
            return getattr(B, f'w_{s}')

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

    def spy_get_w_type(self, vm: 'SPyVM') -> W_Type:
        return self.w_functype

    def spy_call(self, vm: 'SPyVM', args_w: list[W_Object]) -> W_Object:
        raise NotImplementedError


class W_ASTFunc(W_Func):
    fqn: FQN
    closure: tuple[Namespace, ...]
    funcdef: ast.FuncDef
    # types of local variables: this is non-None IIF the function has been
    # redshifted.
    locals_types_w: Optional[dict[str, W_Type]]

    def __init__(self,
                 fqn: FQN,
                 closure: tuple[Namespace, ...],
                 w_functype: W_FuncType,
                 funcdef: ast.FuncDef,
                 *,
                 locals_types_w: Optional[dict[str, W_Type]] = None
                 ) -> None:
        self.fqn = fqn
        self.closure = closure
        self.w_functype = w_functype
        self.funcdef = funcdef
        self.locals_types_w = locals_types_w

    @property
    def redshifted(self):
        return self.locals_types_w is not None

    def __repr__(self) -> str:
        if self.redshifted:
            return f"<spy function '{self.fqn}' (redshifted)>"
        else:
            return f"<spy function '{self.fqn}'>"


class W_BuiltinFunc(W_Func):
    fqn: FQN

    def __init__(self, fqn: FQN, w_functype: W_FuncType) -> None:
        self.fqn = fqn
        self.w_functype = w_functype

    def __repr__(self) -> str:
        return f"<spy function '{self.fqn}' (builtin)>"

    def spy_call(self, vm: 'SPyVM', args_w: list[W_Object]) -> W_Object:
        # XXX we need a way to automatically generate unwrapping code for
        # args_w. For now, let's just hardcode
        if self.w_functype.name == 'def(x: i32) -> i32':
            assert len(args_w) == 1
            arg = vm.unwrap_i32(args_w[0])
            res = vm.ll.call(self.fqn.c_name, arg)
            return vm.wrap(res)
        else:
            assert False
