from typing import TYPE_CHECKING
from types import NoneType
from spy import ast
from spy.fqn import FQN
from spy.errors import (SPyRuntimeAbort, SPyTypeError, SPyNameError,
                        SPyRuntimeError)
from spy.location import Loc
from spy.vm.object import W_Object, W_Type
from spy.vm.builtins import B
from spy.util import magic_dispatch
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

class TypeChecker:
    vm: 'SPyVM'
    modname: str
    locals_loc: dict[str, Loc]
    locals_types_w: dict[str, W_Type]

    def __init__(self, vm: 'SPyVM', modname: str):
        self.vm = vm
        self.modname = modname
        self.locals_loc = {}
        self.locals_types_w = {}

    def declare_local(self, loc: Loc, name: str, w_type: W_Type) -> None:
        assert name not in self.locals_loc, f'variable already declared: {name}'
        self.locals_loc[name] = loc
        self.locals_types_w[name] = w_type

    def typecheck_local(self, got_loc: Loc, name: str, w_got: W_Object) -> None:
        assert name in self.locals_loc
        w_type = self.locals_types_w[name]
        loc = self.locals_loc[name]
        if self.vm.is_compatible_type(w_got, w_type):
            return
        err = SPyTypeError('mismatched types')
        got = self.vm.dynamic_type(w_got).name
        exp = w_type.name
        exp_loc = loc
        err.add('error', f'expected `{exp}`, got `{got}`', loc=got_loc)
        if name == '@return':
            because = 'because of return type'
        else:
            because = 'because of type declaration'
        err.add('note', f'expected `{exp}` {because}', loc=exp_loc)
        raise err

    def check_expr(self, expr: ast.Expr) -> W_Type:
        """
        Compute the STATIC type of the given expression
        """
        return magic_dispatch(self, 'check_expr', expr)

    def check_expr_Name(self, name: ast.Name) -> W_Type:
        if name.scope == 'local':
            return self.locals_types_w[name.id]
        elif name.scope in ('module', 'builtins'):
            if name.scope == 'builtins':
                fqn = FQN(modname='builtins', attr=name.id)
            else:
                fqn = FQN(modname=self.modname, attr=name.id)

            # XXX this is wrong: we should keep track of the static type of
            # FQNs. For now, we just look it up and use the dynamic type
            w_value = self.vm.lookup_global(fqn)
            assert w_value is not None
            return self.vm.dynamic_type(w_value)
        elif name.scope == 'non-declared':
            msg = f"name `{name.id}` is not defined"
            raise SPyNameError.simple(msg, "not found in this scope", name.loc)
        elif name.scope == "unknown":
            assert False, "bug in the ScopeAnalyzer?"
        else:
            assert False, f"Invalid value for scope: {name.scope}"


        assert False, 'WIP'

    def check_expr_Constant(self, const: ast.Constant) -> W_Type:
        T = type(const.value)
        assert T in (int, bool, str, NoneType)
        if T is int:
            return B.w_i32
        elif T is bool:
            return B.w_bool
        elif T is str:
            return B.w_str
        elif T is NoneType:
            return B.w_void
        assert False
