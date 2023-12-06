from typing import Optional
from spy import ast
from spy.location import Loc
from spy.fqn import FQN
from spy.errors import SPyTypeError, SPyImportError, SPyScopeError, maybe_plural
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
    stack: list[SymTable]
    funcdef_scopes: dict[ast.FuncDef, SymTable]

    def __init__(self, vm: SPyVM, modname: str, mod: ast.Module) -> None:
        self.vm = vm
        self.mod = mod
        self.builtins_scope = SymTable.from_builtins(vm)
        self.mod_scope = SymTable(modname)
        self.stack = []
        self.funcdef_scopes = {}
        self.push_scope(self.builtins_scope)
        self.push_scope(self.mod_scope)


    # ===============
    # public API
    # ================

    def analyze(self) -> None:
        assert len(self.stack) == 2 # [builtins, module]
        for decl in self.mod.decls:
            self.declare(decl)
        assert len(self.stack) == 2

        for decl in self.mod.decls:
            self.flatten(decl)
        assert len(self.stack) == 2

    def by_module(self) -> SymTable:
        return self.mod_scope

    def by_funcdef(self, funcdef: ast.FuncDef) -> SymTable:
        return self.funcdef_scopes[funcdef]

    # =====

    def push_scope(self, scope: SymTable) -> None:
        self.stack.append(scope)

    def pop_scope(self) -> SymTable:
        return self.stack.pop()

    @property
    def scope(self) -> SymTable:
        """
        Return the currently active scope
        """
        return self.stack[-1]

    def lookup(self, name: str) -> tuple[int, Optional[Symbol]]:
        """
        Lookup a name, starting from the innermost scope, towards the outer.
        """
        for level, scope in enumerate(reversed(self.stack)):
            if name in scope:
                return level, scope.lookup(name)
        # not found
        return -1, None

    def add_name(self, name: str, color: ast.Color,
                 loc: Loc, type_loc: Loc) -> None:
        """
        Add a name to the current scope.

        The level of the new symbol will be 0.
        """
        level, sym = self.lookup(name)
        if sym and name != '@return':
            if level == 0:
                # re-declaration in the same scope
                msg = f'variable `{name}` already declared'
            else:
                # shadowing a name in an outer scope
                msg = (f'variable `{name}` shadows a name declared ' +
                       "in an outer scope")
            err = SPyScopeError(msg)
            err.add('error', 'this is the new declaration', loc)
            err.add('note', 'this is the previous declaration', sym.loc)
            raise err

        if self.scope is self.mod_scope:
            # this is a module-level global. Let's give it a FQN
            fqn = FQN(modname=self.mod_scope.name, attr=name)
        else:
            fqn = None

        sym = Symbol(name, color, loc=loc, type_loc=type_loc, fqn=fqn, level=0)
        self.scope.add(sym)

    # ====

    def declare(self, node: ast.Node) -> None:
        """
        Visit all the nodes which introduce a new name in the scope, and declare
        those names.
        """
        return node.visit('declare', self)

    def declare_GlobalVarDef(self, decl: ast.GlobalVarDef) -> None:
        self.add_name(decl.vardef.name, 'blue', decl.loc, decl.vardef.type.loc)

    def declare_VarDef(self, vardef: ast.VarDef) -> None:
        self.add_name(vardef.name, 'red', vardef.loc, vardef.type.loc)

    def declare_FuncDef(self, funcdef: ast.FuncDef) -> None:
        # declare the func in the "outer" scope
        self.add_name(funcdef.name, 'blue', funcdef.loc, funcdef.loc)
        inner_scope = SymTable(funcdef.name)
        self.push_scope(inner_scope)
        self.funcdef_scopes[funcdef] = inner_scope
        for arg in funcdef.args:
            self.add_name(arg.name, 'red', arg.loc, arg.type.loc)
        self.add_name('@return', 'red', funcdef.return_type.loc,
                      funcdef.return_type.loc)
        for stmt in funcdef.body:
            self.declare(stmt)
        self.pop_scope()

    def declare_Assign(self, assign: ast.Assign) -> None:
        # if target name does not exist elsewhere, we treat it as an implicit
        # declaration
        name = assign.target
        level, sym = self.lookup(name)
        if sym is None:
            # we don't have an explicit type annotation: we consider the
            # "value" to be the type_loc, because it's where the type will be
            # computed from
            type_loc = assign.value.loc
            self.add_name(name, 'red', assign.loc, type_loc)

    # ===

    def capture_maybe(self, varname: str) -> None:
        level, sym = self.lookup(varname)
        if level in (-1, 0):
            # name already in the symtable, or NameError. Nothing to do here.
            return
        # the name was found but in an outer scope. Let's "capture" it.
        assert sym
        new_sym = sym.replace(level=level)
        assert varname not in self.scope
        self.scope.add(new_sym)

    def flatten(self, node: ast.Node) -> None:
        """
        Visit all the nodes in the AST and flatten the symtables of all the
        FuncDefs.

        In particular, introduce a symbol for every Name which is used inside
        a function but defined in some outer scope.
        """
        return node.visit('flatten', self)

    def flatten_FuncDef(self, funcdef: ast.FuncDef) -> None:
        # the TYPES of the arguments are evaluated in the outer scope
        self.flatten(funcdef.return_type)
        for arg in funcdef.args:
            self.flatten(arg)
        #
        # the statements of the function are evaluated in the inner scope
        inner_scope = self.by_funcdef(funcdef)
        self.push_scope(inner_scope)
        for stmt in funcdef.body:
            self.flatten(stmt)
        self.pop_scope()
        #
        funcdef.symtable = inner_scope

    def flatten_Name(self, name: ast.Name) -> None:
        self.capture_maybe(name.id)

    def flatten_Assign(self, assign: ast.Assign) -> None:
        self.capture_maybe(assign.target)
