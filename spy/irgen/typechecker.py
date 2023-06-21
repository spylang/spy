from typing import NoReturn, Optional
import ast as py_ast
import spy.ast
from spy.location import Loc
from spy.errors import SPyTypeError
from spy.irgen.symtable import SymTable
from spy.vm.vm import SPyVM
from spy.vm.object import W_Type
from spy.vm.function import W_FunctionType
from spy.util import magic_dispatch

def can_assign_to(w_type_from: W_Type, w_type_to: W_Type) -> bool:
    # XXX this is wrong, but better than nothing for now
    return w_type_from == w_type_to


class TypeChecker:
    vm: SPyVM
    mod: spy.ast.Module
    funcdef_types: dict[spy.ast.FuncDef, W_FunctionType]
    funcdef_scopes: dict[spy.ast.FuncDef, SymTable]
    expr_types: dict[py_ast.expr, W_Type]

    def __init__(self, vm: SPyVM, mod: spy.ast.Module) -> None:
        self.vm = vm
        self.mod = mod
        self.global_scope = SymTable('<globals>', parent=None) # XXX should be builtins
        self.funcdef_types = {}
        self.funcdef_scopes = {}
        self.expr_types = {}

    # ===============
    # public API
    # ================

    def check_everything(self) -> None:
        self.check_Module(self.mod, self.global_scope)

    def get_expr_type(self, expr: py_ast.expr) -> W_Type:
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

    # ===============
    # implementation
    # ===============

    def record_expr(self, expr: py_ast.expr, w_type: W_Type) -> None:
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

    def resolve_type(self, expr: py_ast.expr) -> W_Type:
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

        w_type = self.vm.builtins.lookup(typename)
        if w_type is None:
            self.error(f'cannot find type `{typename}`',
                       'not found in this scope', expr.loc)
        if not isinstance(w_type, W_Type):
            got = self.vm.dynamic_type(w_type).name
            self.error(f'{typename} is not a type',
                       f'this is a `{got}`', expr.loc)
        #
        return w_type

    def ensure_Name(self, expr: py_ast.expr) -> Optional[str]:
        """
        Return the name as a string, or None if the expr is not a Name.
        """
        if isinstance(expr, py_ast.Name):
            return expr.id
        return None

    def declare(self, decl: spy.ast.Decl, scope: SymTable) -> None:
        return magic_dispatch(self, 'declare', decl, scope)

    def check(self, decl: spy.ast.Decl, scope: SymTable) -> None:
        return magic_dispatch(self, 'check', decl, scope)

    def check_stmt(self, node: spy.ast.AnyNode, scope: SymTable) -> None:
        return magic_dispatch(self, 'check_stmt', node, scope)

    def check_expr(self, expr: py_ast.expr, scope: SymTable) -> W_Type:
        w_type = magic_dispatch(self, 'check_expr', expr, scope)
        self.record_expr(expr, w_type)
        return w_type

    # =====

    def check_stmt_NotImplemented(self, node: py_ast.AST,
                                  scope: SymTable) -> NoReturn:
        """
        Emit a nice error in case we encounter an unsupported AST node.

        In theory this should belong to the parser, but since we are passing
        around py_ast.{expr,stmt} untouched, this is the easiest place where
        to detect them.
        """
        thing = node.__class__.__name__
        self.error(f'not implemented yet: {thing}',
                   'this is not yet supported by SPy', node.loc)
    check_expr_NotImplemented = check_stmt_NotImplemented

    # =====

    def check_Module(self, mod: spy.ast.Module, scope: SymTable) -> None:
        for decl in mod.decls:
            self.declare(decl, scope)
        for decl in mod.decls:
            self.check(decl, scope)

    def declare_FuncDef(self, funcdef: spy.ast.FuncDef, scope: SymTable) -> None:
        argtypes_w = [self.resolve_type(arg.type) for arg in funcdef.args]
        w_return_type = self.resolve_type(funcdef.return_type)
        w_functype = W_FunctionType(argtypes_w, w_return_type)
        scope.declare(funcdef.name, w_functype, funcdef.loc)
        self.funcdef_types[funcdef] = w_functype

    def check_FuncDef(self, funcdef: spy.ast.FuncDef, outer_scope: SymTable) -> None:
        local_scope = SymTable(funcdef.name, parent=outer_scope)
        self.funcdef_scopes[funcdef] = local_scope
        w_functype = self.funcdef_types[funcdef]
        local_scope.declare('@return', w_functype.w_restype, funcdef.return_type.loc)
        for stmt in funcdef.body:
            self.check_stmt(stmt, local_scope)

    # ==== statements ====

    def check_stmt_AnnAssign(self, assign: py_ast.AnnAssign,
                             scope: SymTable) -> None:
        """
        This is our way of declaring variables (for now):
            x: i32 = <expr>
        """
        # XXX: we probably want to have a declaration pass, to detect cases in
        # which the variable is declared below but not yet (and report a
        # meaningful error)
        varname = self.ensure_Name(assign.target)
        if varname is None:
            # I don't think it's possible to generate an AnnAssign node with a
            # non-name target
            assert False, 'WTF?'
        #
        existing_sym = scope.lookup(varname)
        if existing_sym:
            err = SPyTypeError(f'variable `{varname}` already declared')
            err.add('error', 'this is the new declaration', assign.loc)
            err.add('note', 'this is the previous declaration', existing_sym.loc)
            raise err
        #
        w_declared_type = self.resolve_type(assign.annotation)
        scope.declare(varname, w_declared_type, assign.loc)
        #
        assert assign.value is not None
        w_type = self.check_expr(assign.value, scope)
        if not can_assign_to(w_type, w_declared_type):
            self.raise_type_mismatch(w_declared_type,
                                     assign.loc,
                                     w_type,
                                     assign.value.loc,
                                     'because of type declaration')

    def check_stmt_Return(self, ret: py_ast.Return, scope: SymTable) -> None:
        assert ret.value is not None # XXX implement better error
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

    # ==== expressions ====

    def check_expr_Constant(self, const: py_ast.Constant, scope: SymTable) -> W_Type:
        T = type(const.value)
        if T is int:
            return self.vm.builtins.w_i32
        else:
            self.error(f'unsupported literal: {const.value!r}',
                       f'this is not supported', const.loc)

    def check_expr_Name(self, expr: py_ast.Name, scope: SymTable) -> W_Type:
        varname = expr.id
        sym = scope.lookup(varname)
        if not sym:
            err = SPyTypeError(f'cannot find variable `{varname}` in this scope')
            err.add('error', 'not found in this scope', expr.loc)
            raise err
        return sym.w_type
