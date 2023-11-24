from spy import ast
from spy.errors import SPyTypeError, SPyImportError, maybe_plural
from spy.irgen.symtable import SymTable, Symbol
from spy.irgen import multiop
from spy.vm.vm import SPyVM
from spy.util import magic_dispatch


class ScopeAnalyzer:
    """
    Visit the given AST Module and determine the scope of each name.

    The scoping rules for SPy are very simple for now:

      - names declared at module-level scopes are always available to all
        their inner scopes

      - inside a function, assigment declares a local variable ONLY if this
        name does not exist in an outer scope. Note that this is different
        from Python rules. No more 'global' and 'nonlocal' declarations.

      - shadowing a name is an error

    In the future, we might want to introduce a special compatibility mode to
    use Python's rules to make porting easier, e.g. by using `from __python__
    import scoping_rules`, but for now it's not a priority.
    """
    vm: SPyVM
    mod: ast.Module
    funcdef_scopes: dict[ast.FuncDef, SymTable]

    def __init__(self, vm: SPyVM, modname: str, mod: ast.Module) -> None:
        self.vm = vm
        self.mod = mod
        self.builtins_scope = SymTable.from_builtins(vm)
        self.mod_scope = SymTable(modname, parent=self.builtins_scope)
        self.funcdef_scopes = {}

    # ===============
    # public API
    # ================

    def analyze(self) -> None:
        for decl in self.mod.decls:
            self.visit(decl, self.mod_scope)
        ## for decl in mod.decls:
        ##     self.check(decl, scope)

    def by_module(self) -> SymTable:
        return self.mod_scope

    def by_funcdef(self, funcdef: ast.FuncDef) -> SymTable:
        return self.funcdef_scopes[funcdef]

    # =====

    def visit(self, node: ast.Node, scope: SymTable) -> None:
        return magic_dispatch(self, 'visit', node, scope)

    # ====

    def visit_GlobalFuncDef(self, decl: ast.GlobalFuncDef,
                            scope: SymTable) -> None:
        self.visit(decl.funcdef, scope)

    def visit_GlobalVarDef(self, decl: ast.GlobalVarDef,
                           scope: SymTable) -> None:
        scope.declare(decl.vardef.name, 'blue', decl.loc)

    def visit_FuncDef(self, funcdef: ast.FuncDef, scope: SymTable) -> None:
        scope.declare(funcdef.name, 'blue', funcdef.loc)
        inner_scope = SymTable(funcdef.name, parent=scope)
        self.funcdef_scopes[funcdef] = inner_scope
        for arg in funcdef.args:
            inner_scope.declare(arg.name, 'red', arg.loc)
        for stmt in funcdef.body:
            self.visit(stmt, inner_scope)

    def visit_VarDef(self, vardef: ast.VarDef, scope: SymTable) -> None:
        scope.declare(vardef.name, 'red', vardef.loc)

    def visit_Assign(self, assign: ast.Assign, scope: SymTable) -> None:
        scope.declare(assign.target, 'red', assign.loc)

    def visit_Pass(self, node: ast.Pass, scope: SymTable) -> None:
        pass
