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

    def error(self, loc: Loc, message: str) -> NoReturn:
        raise SPyTypeError(loc, message)

    def resolve_type(self, expr: py_ast.expr) -> W_Type:
        # OK, this is very wrong. We should have a proper table of types with
        # the possibility of nested scopes and lookups. For now, we just to a
        # hardcoded lookup in the VM builtins, which is good enough to resolve
        # builtin types.
        #
        # Also, eventually we should support arbitrary expressions, but for
        # now we just support simple Names.
        if not isinstance(expr, py_ast.Name):
            self.error(expr.loc, f'Only simple types are supported for now')
        #
        w_type = self.vm.builtins.lookup(expr.id)
        if w_type is None:
            self.error(expr.loc, f'Unknown type: {expr.id}')
        if not isinstance(w_type, W_Type):
            self.error(expr.loc, f'{expr.id} is not a type')
        #
        return w_type

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

    def check_stmt_Return(self, ret: py_ast.Return, scope: SymTable) -> None:
        assert ret.value is not None # XXX implement better error
        return_sym = scope.lookup('@return')
        assert return_sym is not None
        #
        w_type = self.check_expr(ret.value, scope)
        if not can_assign_to(w_type, return_sym.w_type):
            import pdb;pdb.set_trace()
            self.error(ret.loc, 'XXX')

    def check_expr_Constant(self, const: py_ast.Constant, scope: SymTable) -> W_Type:
        T = type(const.value)
        if T is int:
            return self.vm.builtins.w_i32
        else:
            self.error(const.loc, f'Unsupported literal: {const.value}')
