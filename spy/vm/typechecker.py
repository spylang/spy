from typing import TYPE_CHECKING, Optional, NoReturn
from types import NoneType
from spy import ast
from spy.fqn import FQN
from spy.irgen.symtable import Symbol
from spy.errors import (SPyTypeError, SPyNameError, maybe_plural)
from spy.location import Loc
from spy.vm.object import W_Object, W_Type
from spy.vm.function import W_FuncType
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

    def check_expr_BinOp(self, binop: ast.BinOp) -> W_Type:
        w_ltype = self.check_expr(binop.left)
        w_rtype = self.check_expr(binop.right)
        if w_ltype is B.w_i32 and w_rtype is B.w_i32:
            return B.w_i32
        #
        lt = w_ltype.name
        rt = w_rtype.name
        err = SPyTypeError(f'cannot do `{lt}` {binop.op} `{rt}`')
        err.add('error', f'this is `{lt}`', binop.left.loc)
        err.add('error', f'this is `{rt}`', binop.right.loc)
        raise err

    check_expr_Add = check_expr_BinOp
    check_expr_Mul = check_expr_BinOp

    def check_expr_Call(self, call: ast.Call) -> W_Type:
        sym = None # XXX find the loc where the function is defined
        w_functype = self.check_expr(call.func)
        if not isinstance(w_functype, W_FuncType):
            self._call_error_non_callable(call, sym, w_functype)
        #
        argtypes_w = [self.check_expr(arg) for arg in call.args]
        got_nargs = len(argtypes_w)
        exp_nargs = len(w_functype.params)
        if got_nargs != exp_nargs:
            self._call_error_wrong_argcount(call, sym, got_nargs, exp_nargs)
        #
        for i, (param, w_arg_type) in enumerate(zip(w_functype.params,
                                                    argtypes_w)):
            if not self.vm.can_assign_from_to(w_arg_type, param.w_type):
                self._call_error_type_mismatch(call, sym, i,
                                               w_exp_type = param.w_type,
                                               w_got_type = w_arg_type)
        #
        return w_functype.w_restype


    def _call_error_non_callable(self, call: ast.Call,
                                 sym: Optional[Symbol],
                                 w_type: W_Type) -> NoReturn:
        err = SPyTypeError(f'cannot call objects of type `{w_type.name}`')
        err.add('error', 'this is not a function', call.func.loc)
        if sym:
            err.add('note', 'variable defined here', sym.loc)
        raise err

    def _call_error_wrong_argcount(self, call: ast.Call,
                                   sym: Optional[Symbol],
                                   got: int, exp: int) -> NoReturn:
        assert got != exp
        takes = maybe_plural(exp, f'takes {exp} argument')
        supplied = maybe_plural(got,
                                f'1 argument was supplied',
                                f'{got} arguments were supplied')
        err = SPyTypeError(f'this function {takes} but {supplied}')
        #
        if got < exp:
            diff = exp - got
            arguments = maybe_plural(diff, 'argument')
            err.add('error', f'{diff} {arguments} missing', call.func.loc)
        else:
            diff = got - exp
            arguments = maybe_plural(diff, 'argument')
            first_extra_arg = call.args[exp]
            last_extra_arg = call.args[-1]
            # XXX this assumes that all the arguments are on the same line
            loc = first_extra_arg.loc.replace(
                col_end = last_extra_arg.loc.col_end
            )
            err.add('error', f'{diff} extra {arguments}', loc)
        #
        if sym:
            err.add('note', 'function defined here', sym.loc)
        raise err

    def _call_error_type_mismatch(self,
                                  call: ast.Call,
                                  sym: Optional[Symbol],
                                  i: int,
                                  w_exp_type: W_Type,
                                  w_got_type: W_Type
                                  ) -> NoReturn:
        err = SPyTypeError('mismatched types')
        exp = w_exp_type.name
        got = w_got_type.name
        err.add('error', f'expected `{exp}`, got `{got}`', call.args[i].loc)
        if sym:
            err.add('note', 'function defined here', sym.loc)
        raise err