from typing import TYPE_CHECKING
from spy import ast
from spy.errors import (SPyRuntimeAbort, SPyTypeError, SPyNameError,
                        SPyRuntimeError)
from spy.location import Loc
from spy.vm.object import W_Object, W_Type
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

class TypeChecker:
    locals_loc: dict[str, Loc]
    locals_types_w: dict[str, W_Type]

    def __init__(self, vm: 'SPyVM'):
        self.vm = vm
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

    ## def check_expr(self, expr: ast.Expr) -> W_Type:
    ##     """
    ##     Compute the STATIC type of the given expression
    ##     """
    ##     magic_dispatch(...)
