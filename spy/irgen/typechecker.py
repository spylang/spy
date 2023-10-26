from typing import NoReturn, Optional
from types import NoneType
import spy.ast
from spy.location import Loc
from spy.errors import SPyTypeError, maybe_plural
from spy.irgen.symtable import SymTable, Symbol
from spy.irgen import multiop
from spy.vm.vm import SPyVM, Builtins as B
from spy.vm.object import W_Type, W_Object
from spy.vm.function import W_FunctionType, FuncParam
from spy.util import magic_dispatch

def can_assign_to(w_type_from: W_Type, w_type_to: W_Type) -> bool:
    # XXX this is wrong, but better than nothing for now
    return w_type_from == w_type_to


class TypeChecker:
    vm: SPyVM
    mod: spy.ast.Module
    funcdef_types: dict[spy.ast.FuncDef, W_FunctionType]
    funcdef_scopes: dict[spy.ast.FuncDef, SymTable]
    expr_types: dict[spy.ast.Expr, W_Type]
    consts_w: dict[spy.ast.Constant, W_Object]

    def __init__(self, vm: SPyVM, mod: spy.ast.Module) -> None:
        self.vm = vm
        self.mod = mod
        self.builtins_scope = SymTable.from_builtins(vm)
        self.global_scope = SymTable('<globals>', parent=self.builtins_scope)
        self.funcdef_types = {}
        self.funcdef_scopes = {}
        self.expr_types = {}
        self.consts_w = {}

    # ===============
    # public API
    # ================

    def check_everything(self) -> None:
        self.check_Module(self.mod, self.global_scope)

    def get_expr_type(self, expr: spy.ast.Expr) -> W_Type:
        """
        Return the W_Type of the given AST expression.

        This assumes that typechecking already happened and it was successful.
        """
        assert expr in self.expr_types, \
            'probably a bug in the typechecker, some AST node was not visited?'
        return self.expr_types[expr]

    def get_funcdef_info(self, funcdef: spy.ast.FuncDef) \
                                                  -> tuple[W_FunctionType, SymTable]:
        w_type = self.funcdef_types[funcdef]
        scope = self.funcdef_scopes[funcdef]
        return w_type, scope

    def get_w_const(self, const: spy.ast.Constant) -> W_Object:
        """
        Convert a spy.ast.Constant into the equivalent w_* value.
        """
        if const in self.consts_w:
            return self.consts_w[const]
        #
        # not found, make it
        w_const = None
        T = type(const.value)
        if T in (int, bool, str, NoneType):
            w_const = self.vm.wrap(const.value)
        else:
            self.error(f'unsupported literal: {const.value!r}',
                       f'this is not supported', const.loc)
        #
        self.consts_w[const] = w_const
        return w_const

    # ===============
    # implementation
    # ===============

    def record_expr(self, expr: spy.ast.Expr, w_type: W_Type) -> None:
        assert expr not in self.expr_types
        self.expr_types[expr] = w_type

    def error(self, primary: str, secondary: str, loc: Loc) -> NoReturn:
        raise SPyTypeError.simple(primary, secondary, loc)

    def raise_type_mismatch(self, w_exp_type: W_Type, exp_loc: Loc,
                            w_got_type: W_Type, got_loc: Loc,
                            because: str) -> NoReturn:
        err = SPyTypeError('mismatched types')
        got = w_got_type.name
        exp = w_exp_type.name
        err.add('error', f'expected `{exp}`, got `{got}`', loc=got_loc)
        err.add('note', f'expected `{exp}` {because}', loc=exp_loc)
        raise err

    def resolve_type(self, expr: spy.ast.Expr) -> W_Type:
        # OK, this is very wrong. We should have a proper table of types with
        # the possibility of nested scopes and lookups. For now, we just to a
        # hardcoded lookup in the VM builtins, which is good enough to resolve
        # builtin types.
        #
        # Also, eventually we should support arbitrary expressions, but for
        # now we just support simple Names.
        typename = self.ensure_Name(expr)
        if not typename:
            self.error('only simple types are supported for now',
                       'this expression is too complex', expr.loc)

        w_type = B.lookup(typename)
        if w_type is None:
            self.error(f'cannot find type `{typename}`',
                       'not found in this scope', expr.loc)
        if not isinstance(w_type, W_Type):
            got = self.vm.dynamic_type(w_type).name
            self.error(f'{typename} is not a type',
                       f'this is a `{got}`', expr.loc)
        #
        return w_type

    def ensure_Name(self, expr: spy.ast.Expr) -> Optional[str]:
        """
        Return the name as a string, or None if the expr is not a Name.
        """
        if isinstance(expr, spy.ast.Name):
            return expr.id
        return None

    def lookup_Name_maybe(self, expr: spy.ast.Expr, scope: SymTable) -> Optional[Symbol]:
        """
        Try to get the place where expr was defined, in case expr is a Name.
        """
        if isinstance(expr, spy.ast.Name):
            return scope.lookup(expr.id)
        return None

    def declare(self, decl: spy.ast.Decl, scope: SymTable) -> None:
        return magic_dispatch(self, 'declare', decl, scope)

    def check(self, decl: spy.ast.Decl, scope: SymTable) -> None:
        return magic_dispatch(self, 'check', decl, scope)

    def check_stmt(self, node: spy.ast.AnyNode, scope: SymTable) -> None:
        return magic_dispatch(self, 'check_stmt', node, scope)

    def check_expr(self, expr: spy.ast.Expr, scope: SymTable) -> W_Type:
        w_type = magic_dispatch(self, 'check_expr', expr, scope)
        self.record_expr(expr, w_type)
        return w_type

    # =====

    def check_Module(self, mod: spy.ast.Module, scope: SymTable) -> None:
        for decl in mod.decls:
            self.declare(decl, scope)
        for decl in mod.decls:
            self.check(decl, scope)

    def declare_FuncDef(self, funcdef: spy.ast.FuncDef, scope: SymTable) -> None:
        params = [
            FuncParam(
                name = arg.name,
                w_type = self.resolve_type(arg.type)
            )
            for arg in funcdef.args
        ]
        w_return_type = self.resolve_type(funcdef.return_type)
        w_functype = W_FunctionType(params, w_return_type)
        scope.declare(funcdef.name, 'const', w_functype, funcdef.loc)
        self.funcdef_types[funcdef] = w_functype

    def check_FuncDef(self, funcdef: spy.ast.FuncDef, outer_scope: SymTable) -> None:
        local_scope = SymTable(funcdef.name, parent=outer_scope)
        self.funcdef_scopes[funcdef] = local_scope
        w_functype = self.funcdef_types[funcdef]
        #
        # add function arguments to the local scope
        local_scope.declare('@return', 'var', w_functype.w_restype,
                            funcdef.return_type.loc)
        assert len(funcdef.args) == len(w_functype.params)
        for arg_node, param in zip(funcdef.args, w_functype.params):
            local_scope.declare(param.name, 'var', param.w_type, arg_node.loc)
        #
        for stmt in funcdef.body:
            self.check_stmt(stmt, local_scope)

    def declare_GlobalVarDef(self, globvar: spy.ast.GlobalVarDef, scope: SymTable) -> None:
        # only constants are allowed as initializers, for now
        vardef = globvar.vardef
        if not isinstance(vardef.value, spy.ast.Constant):
            assert False
        #
        # this seems weird but it's actually correct. At this point, we only
        # want to declare module-level vars and functions: we don't want to
        # *check* statements because in theory they could reference names
        # which have not been declared yet (precisely because we are declaring
        # them now). However, here we know for sure that vardef.value is a
        # Constant, so this is safe to do.
        self.check_stmt_VarDef(vardef, scope)

    def check_GlobalVarDef(self, globvar: spy.ast.GlobalVarDef, scope: SymTable) -> None:
        # nothing to do, we did everything inside declare()
        pass

    def declare_Import(self, imp: spy.ast.Import, scope: SymTable) -> None:
        w_obj = self.vm.lookup(imp.fqn)
        # ouch, this is slightly wrong: we don't want the dynamic type, we
        # want the static/declared type. XXX fix
        w_type = self.vm.dynamic_type(w_obj)
        scope.declare(imp.asname, 'const', w_type, imp.loc)

    def check_Import(self, imp: spy.ast.Import, scope: SymTable) -> None:
        pass

    # ==== statements ====

    def check_stmt_VarDef(self, vardef: spy.ast.VarDef, scope: SymTable) -> None:
        """
        This is our way of declaring variables (for now):
            x: i32 = <expr>
        """
        # XXX: we probably want to have a declaration pass, to detect cases in
        # which the variable is declared below but not yet (and report a
        # meaningful error)
        #
        existing_sym = scope.lookup(vardef.name)
        if existing_sym:
            err = SPyTypeError(f'variable `{vardef.name}` already declared')
            err.add('error', 'this is the new declaration', vardef.loc)
            err.add('note', 'this is the previous declaration', existing_sym.loc)
            raise err
        #
        w_declared_type = self.resolve_type(vardef.type)
        scope.declare(vardef.name, 'var', w_declared_type, vardef.loc)
        #
        assert vardef.value is not None, 'TODO'
        w_type = self.check_expr(vardef.value, scope)
        if not can_assign_to(w_type, w_declared_type):
            self.raise_type_mismatch(w_declared_type,
                                     vardef.loc,
                                     w_type,
                                     vardef.value.loc,
                                     'because of type declaration')

    def check_stmt_StmtExpr(self, stmt: spy.ast.StmtExpr, scope: SymTable) -> None:
        self.check_expr(stmt.value, scope)

    def check_stmt_Assign(self, assign: spy.ast.Assign, scope: SymTable) -> None:
        varname = assign.target
        w_valuetype = self.check_expr(assign.value, scope)
        sym = scope.lookup(varname)
        if not sym:
            err = SPyTypeError(f'variable `{varname}` is not declared')
            err.add('error', 'this is not declared', assign.target_loc)
            hint = (f'hint: to declare a new variable, you can use: ' +
                    f'`{varname}: {w_valuetype.name} = ...`')
            err.add('note', hint, assign.loc)
            raise err
        if not can_assign_to(w_valuetype, sym.w_type):
            self.raise_type_mismatch(sym.w_type,
                                     sym.loc,
                                     w_valuetype,
                                     assign.value.loc,
                                     'because of type declaration')



    def check_stmt_Return(self, ret: spy.ast.Return, scope: SymTable) -> None:
        return_sym = scope.lookup('@return')
        assert return_sym is not None
        #
        w_type = self.check_expr(ret.value, scope)
        if not can_assign_to(w_type, return_sym.w_type):
            self.raise_type_mismatch(return_sym.w_type,
                                     return_sym.loc,
                                     w_type,
                                     ret.value.loc,
                                     "because of return type")

    def _assert_bool(self, w_type: W_Type, loc: Loc) -> None:
        if w_type is not B.w_bool:
            err = SPyTypeError('mismatched types')
            err.add('error', f'expected `bool`, got `{w_type.name}`', loc)
            err.add('note', f'implicit conversion to `bool` is not implemented yet', loc)
            raise err

    def check_stmt_If(self, if_node: spy.ast.If, scope: SymTable) -> None:
        # XXX do we want to introduce new scopes for if and else?
        w_cond_type = self.check_expr(if_node.test, scope)
        self._assert_bool(w_cond_type, if_node.test.loc)
        for stmt in if_node.then_body:
            self.check_stmt(stmt, scope)
        for stmt in if_node.else_body:
            self.check_stmt(stmt, scope)

    def check_stmt_While(self, while_node: spy.ast.While, scope: SymTable) -> None:
        # same XXX as above: do we want to introduce a new scope inside the loop?
        w_cond_type = self.check_expr(while_node.test, scope)
        self._assert_bool(w_cond_type, while_node.test.loc)
        for stmt in while_node.body:
            self.check_stmt(stmt, scope)

    # ==== expressions ====

    def check_expr_Constant(self, const: spy.ast.Constant, scope: SymTable) -> W_Type:
        # this is a bit suboptimal: we are making the constant and throw it
        # away just to compute the type, and then we re-make it in CodeGen.
        w_const = self.get_w_const(const)
        return self.vm.dynamic_type(w_const)

    def check_expr_Name(self, expr: spy.ast.Name, scope: SymTable) -> W_Type:
        varname = expr.id
        sym = scope.lookup(varname)
        if not sym:
            err = SPyTypeError(f'cannot find variable `{varname}` in this scope')
            err.add('error', 'not found in this scope', expr.loc)
            raise err
        return sym.w_type

    def check_expr_BinOp(self, expr: spy.ast.BinOp, scope: SymTable) -> W_Type:
        w_ltype = self.check_expr(expr.left, scope)
        w_rtype = self.check_expr(expr.right, scope)
        if w_ltype == w_rtype:
            # XXX this is wrong: here we assume that the result of a binop is the
            # same as its arguments, but we need to tweak it when we have
            # e.g. floats and division
            return w_ltype
        elif w_ltype is B.w_str and w_rtype is B.w_i32:
            return B.w_str
        else:
            l = w_ltype.name
            r = w_rtype.name
            err = SPyTypeError(f'cannot do `{l}` {expr.op} `{r}`')
            err.add('error', f'this is `{l}`', expr.left.loc)
            err.add('error', f'this is `{r}`', expr.right.loc)
            raise err

    check_expr_Add = check_expr_BinOp
    check_expr_Mul = check_expr_BinOp

    def check_expr_CompareOp(self, expr: spy.ast.CompareOp, scope: SymTable) -> W_Type:
        w_ltype = self.check_expr(expr.left, scope)
        w_rtype = self.check_expr(expr.right, scope)
        if w_ltype != w_rtype:
            # XXX this is wrong, we need to add support for implicit conversions
            l = w_ltype.name
            r = w_rtype.name
            err = SPyTypeError(f'cannot do `{l}` {expr.op} `{r}`')
            err.add('error', f'this is `{l}`', expr.left.loc)
            err.add('error', f'this is `{r}`', expr.right.loc)
            raise err
        return B.w_bool

    check_expr_Eq = check_expr_CompareOp
    check_expr_NotEq = check_expr_CompareOp
    check_expr_Lt = check_expr_CompareOp
    check_expr_LtE = check_expr_CompareOp
    check_expr_Gt = check_expr_CompareOp
    check_expr_GtE = check_expr_CompareOp

    def check_expr_GetItem(self, expr: spy.ast.GetItem, scope: SymTable) -> W_Type:
        w_vtype = self.check_expr(expr.value, scope)
        w_itype = self.check_expr(expr.index, scope)
        impl = multiop.GetItem.lookup(w_vtype, w_itype)
        if impl:
            return impl.w_restype
        ## if w_vtype is B.w_str:
        ##     if w_itype is B.w_i32:
        ##         return B.w_str
        ##     else:
        ##         err = SPyTypeError('mismatched types')
        ##         got = w_itype.name
        ##         err.add('error', f'expected `i32`, got `{got}`', expr.index.loc)
        ##         err.add('note', f'this is a `str`', expr.value.loc)
        ##         raise err
        else:
            got = w_vtype.name
            err = SPyTypeError(f'`{got}` does not support `[]`')
            err.add('note', f'this is a `{got}`', expr.value.loc)
            raise err

    def check_expr_Call(self, call: spy.ast.Call, scope: SymTable) -> W_Type:
        sym = self.lookup_Name_maybe(call.func, scope) # only used for error reporting
        w_functype = self.check_expr(call.func, scope)
        if not isinstance(w_functype, W_FunctionType):
            self._call_error_non_callable(call, sym, w_functype)
        #
        argtypes_w = [self.check_expr(arg, scope) for arg in call.args]
        got_nargs = len(argtypes_w)
        exp_nargs = len(w_functype.params)
        if got_nargs != exp_nargs:
            self._call_error_wrong_argcount(call, sym, got_nargs, exp_nargs)
        #
        for i, (param, w_arg_type) in enumerate(zip(w_functype.params, argtypes_w)):
            if not can_assign_to(w_arg_type, param.w_type):
                self._call_error_type_mismatch(call, sym, i,
                                               w_exp_type = param.w_type,
                                               w_got_type = w_arg_type)
        #
        return w_functype.w_restype


    def _call_error_non_callable(self, call: spy.ast.Call, sym: Optional[Symbol],
                                 w_type: W_Type) -> NoReturn:
        err = SPyTypeError(f'cannot call objects of type `{w_type.name}`')
        err.add('error', 'this is not a function', call.func.loc)
        if sym:
            err.add('note', 'variable defined here', sym.loc)
        raise err

    def _call_error_wrong_argcount(self, call: spy.ast.Call, sym: Optional[Symbol],
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
            loc = first_extra_arg.loc.replace(col_end=last_extra_arg.loc.col_end)
            err.add('error', f'{diff} extra {arguments}', loc)
        #
        if sym:
            err.add('note', 'function defined here', sym.loc)
        raise err

    def _call_error_type_mismatch(self, call: spy.ast.Call, sym: Optional[Symbol], i: int,
                                  w_exp_type: W_Type, w_got_type: W_Type) -> NoReturn:
        err = SPyTypeError('mismatched types')
        exp = w_exp_type.name
        got = w_got_type.name
        err.add('error', f'expected `{exp}`, got `{got}`', call.args[i].loc)
        if sym:
            err.add('note', 'function defined here', sym.loc)
        raise err
