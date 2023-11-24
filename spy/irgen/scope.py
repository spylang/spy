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
            self.declare(decl, self.mod_scope)
        for decl in self.mod.decls:
            self.set_scope(decl, self.mod_scope)

    def by_module(self) -> SymTable:
        return self.mod_scope

    def by_funcdef(self, funcdef: ast.FuncDef) -> SymTable:
        return self.funcdef_scopes[funcdef]

    # =====

    def declare(self, node: ast.Node, scope: SymTable) -> None:
        return node.visit('declare', self, scope)

    def set_scope(self, node: ast.Node, scope: SymTable) -> None:
        return node.visit('set_scope', self, scope)

    # ====

    def declare_GlobalVarDef(self, decl: ast.GlobalVarDef,
                           scope: SymTable) -> None:
        scope.declare(decl.vardef.name, 'blue', decl.loc)

    def declare_VarDef(self, vardef: ast.VarDef, scope: SymTable) -> None:
        scope.declare(vardef.name, 'red', vardef.loc)

    def declare_FuncDef(self, funcdef: ast.FuncDef,
                        outer_scope: SymTable) -> None:
        outer_scope.declare(funcdef.name, 'blue', funcdef.loc)
        inner_scope = SymTable(funcdef.name, parent=outer_scope)
        self.funcdef_scopes[funcdef] = inner_scope
        for arg in funcdef.args:
            inner_scope.declare(arg.name, 'red', arg.loc)
        for stmt in funcdef.body:
            self.declare(stmt, inner_scope)

    def declare_Assign(self, assign: ast.Assign, scope: SymTable) -> None:
        scope.declare(assign.target, 'red', assign.loc)

    # ===

    def set_scope_FuncDef(self, funcdef: ast.FuncDef,
                          outer_scope: SymTable) -> None:
        inner_scope = self.by_funcdef(funcdef)
        # the TYPES of the arguments are evaluated in the outer scope
        self.set_scope(funcdef.return_type, outer_scope)
        for arg in funcdef.args:
            self.set_scope(arg, outer_scope)
        #
        # the statements of the function are evaluated in the inner scope
        for stmt in funcdef.body:
            self.set_scope(stmt, inner_scope)

    def set_scope_Name(self, name: ast.Name, scope: SymTable) -> None:
        sym = scope.lookup(name.id)
        if sym.scope is scope:
            name.scope = 'local'
        else:
            name.scope = 'nonlocal'
