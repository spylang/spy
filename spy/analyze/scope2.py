from typing import NewType, Optional

from spy import ast
from spy.analyze.symtable import (
    Color,
    ImportRef,
    ScopeKind,
    Symbol,
    SymTable,
    VarKind,
    VarKindOrigin,
    VarStorage,
)
from spy.errors import SPyError
from spy.location import Loc

# SymTable and Scope are similar but conceptually different:
#
#   - `Scope` are created during the bind pass of ScopeAnalyzer, they are nested and
#     they correspond to a lexical scope (including e.g. blocks).
#
#   - `SymTable` is a runtime concept: it's a flat per-function namespace, which
#     contains its local variables
#
# For now Scope and SymTable share the same impl, but they are conceptually different
# beasts
Scope = NewType("Scope", SymTable)

# Key used to look up Scopes in ScopeAnalyzer.scopes.
# The tuple case is for nodes with multiple blocks, like `(ast.If, "then")` and
# `(ast.If, "else")`.
ScopeKey = (
    ast.FuncDef
    | ast.GenericFuncDef
    | ast.ClassDef
    | ast.GenericClassDef
    | tuple[ast.Node, str]
)


class ScopeAnalyzer:
    """
    Visit the given AST Module and determine the scope of each name.

    See docs/src/reference/scoping.md for the full scoping rules.

    The analyzer operates in two passes:

      1. bind: walk all statements that introduce new names (VarDef, FuncDef,
         Import, etc.) and add a Symbol to the current Scope.  After this pass,
         every Scope contains the names directly defined in it (sym.level == 0)
         and is read-only.

         During this pass we also create a SymTable for each FuncDef, and we fill it
         with its locals.

      2. resolve: visit all nodes which needs a name lookup (e.g. ast.Name), and lookup
         the corresponding Symbol.

     Both passes maintain two separate stacks:
     - scope_stack: one Scope per block
     - symtable_stack: one SymTable per FuncDef.

    When we visit a FuncDef node we push both a Scope and a SymTable.
    """

    mod: ast.Module

    scope_stack: list[Scope]
    symtable_stack: list[SymTable]

    scopes: dict[ScopeKey, Scope]  # which scope corresponds to a given Node?
    symtables: dict[ast.Node, SymTable]  # maps FuncDef/ClassDef/etc. to their SymTable

    decl_node: dict[Symbol, ast.Node]  # which node declared a given Symbol?
    seq: dict[ast.Node, int]  # unique seq ID of every node (used by [decl.use-before])
    node_to_sym: dict[ast.Node, Symbol]  # resolved Symbols

    def __init__(self, modname: str, mod: ast.Module) -> None:
        self.mod = mod
        self.mod_symtable = SymTable(modname, "blue", "module")
        self.scope_stack = []
        self.symtable_stack = []
        self.scopes = {}
        self.symtables = {}
        self.seq = {node: i for i, node in enumerate(mod.walk())}
        self.decl_node = {}
        self.node_to_sym = {}

    # ===============
    # public API
    # ================

    def analyze(self) -> None:
        builtins_scope = Scope(SymTable.from_builtins())
        self.push_scope(builtins_scope)
        self.push_scope(Scope(self.mod_symtable))
        # we don't need to push a symtables for builtins
        self.push_symtable(self.mod_symtable)

        # ------- bind pass -------
        assert len(self.scope_stack) == 2  #    [builtins, module]
        assert len(self.symtable_stack) == 1  # [module]
        for decl in self.mod.decls:
            self.bind(decl)

        # ------ resolve pass -----
        assert len(self.scope_stack) == 2  #    [builtins, module]
        assert len(self.symtable_stack) == 1  # [module]
        for decl in self.mod.decls:
            self.resolve(decl)
        assert len(self.symtable_stack) == 1
        assert len(self.scope_stack) == 2

    def by_module(self) -> SymTable:
        return self.mod_symtable

    def by_funcdef(self, funcdef: ast.FuncDef) -> SymTable:
        return self.symtables[funcdef]

    def by_generic_funcdef(self, gfuncdef: ast.GenericFuncDef) -> SymTable:
        return self.symtables[gfuncdef]

    def by_classdef(self, classdef: ast.ClassDef) -> SymTable:
        return self.symtables[classdef]

    def by_generic_classdef(self, gclassdef: ast.GenericClassDef) -> SymTable:
        return self.symtables[gclassdef]

    # =====

    def new_Scope(self, name: str, color: Color, kind: ScopeKind) -> Scope:
        """
        Create a new Scope whose name is derived from the current scope.
        """
        parent = self.scope_stack[-1].name
        fullname = f"{parent}::{name}"
        return Scope(SymTable(fullname, color, kind))

    def push_scope(self, scope: Scope) -> None:
        self.scope_stack.append(scope)

    def pop_scope(self) -> Scope:
        return self.scope_stack.pop()

    def push_symtable(self, symtable: SymTable) -> None:
        self.symtable_stack.append(symtable)

    def pop_symtable(self) -> SymTable:
        return self.symtable_stack.pop()

    @property
    def scope(self) -> Scope:
        """
        Return the currently active lexical scope.
        """
        return self.scope_stack[-1]

    @property
    def symtable(self) -> SymTable:
        """
        Return the currently active SymTable.
        """
        return self.symtable_stack[-1]

    # ====
    # bind pass

    def lookup_ref(self, name: str) -> tuple[int, Optional[Scope], Optional[Symbol]]:
        """
        Lookup a name in the scope_stack, starting from the innermost scope outward.
        """
        for level, scope in enumerate(reversed(self.scope_stack)):
            ## if level > 0 and scope.kind == "class":
            ##     # jump over 'class' scopes
            ##     continue
            if sym := scope.lookup_maybe(name):
                return level, scope, sym
        return -1, None, None

    def lookup_definition(self, name: str) -> tuple[int, Optional[Symbol]]:
        """
        Lookup a name definition, starting from the innermost scope outward.
        """
        for level, scope in enumerate(reversed(self.scope_stack)):
            if sym := scope.lookup_definition_maybe(name):
                return level, sym
        return -1, None

    def create_new_local(
        self,
        node: ast.Node,
        name: str,
        varkind: VarKind,
        varkind_origin: VarKindOrigin,
        loc: Loc,
        type_loc: Loc,
        *,
        impref: Optional[ImportRef] = None,
    ) -> Symbol:
        """
        Add a name definition to the current scope and current symtable (level 0).
        """
        level, scope, sym = self.lookup_ref(name)
        if sym and name != "@return":
            assert scope is not None
            if level == 0:
                msg = f"variable `{name}` already declared"
                err = SPyError("W_ScopeError", msg)
                err.add("error", "this is the new declaration", loc)
                err.add("note", "this is the previous declaration", sym.loc)
                raise err

        storage = "direct"
        ## storage: VarStorage
        ## if self.scope is self.mod_symtable and varkind == "var":
        ##     storage = "cell"
        ## else:
        ##     storage = "direct"

        new_sym = Symbol(
            name,
            varkind,
            varkind_origin,
            storage,
            loc=loc,
            type_loc=type_loc,
            impref=impref,
            level=0,
        )
        self.scope.add(new_sym)
        self.decl_node[new_sym] = node
        return new_sym

    def bind(self, node: ast.Node) -> None:
        return node.visit("bind", self)

    def bind_Import(self, imp: ast.Import) -> None:
        self.create_new_local(
            imp,
            imp.asname,
            "const",
            "auto",
            imp.loc,
            imp.loc,
            impref=imp.ref,
        )

    def bind_GlobalFuncDef(self, decl: ast.GlobalFuncDef) -> None:
        self.bind_FuncDef(decl.funcdef)

    def bind_FuncDef(self, funcdef: ast.FuncDef) -> None:
        # bind the func name in the outer scope
        protoloc = funcdef.prototype_loc
        self.create_new_local(
            funcdef, funcdef.name, "const", "funcdef", protoloc, protoloc
        )

        scope_color = funcdef.color
        if scope_color == "red":
            argkind: VarKind = "var"
            argkind_origin: VarKindOrigin = "red-param"
        else:
            assert False
            ## argkind = "const"
            ## argkind_origin = "blue-param"

        inner_scope = self.new_Scope(funcdef.name, scope_color, "function")
        symtable = SymTable(funcdef.name, scope_color, "function")
        self.push_scope(inner_scope)
        self.push_symtable(symtable)
        self.scopes[funcdef] = inner_scope
        self.symtables[funcdef] = symtable

        for arg in funcdef.args:
            sym = self.create_new_local(
                arg,
                arg.name,
                argkind,
                argkind_origin,
                arg.loc,
                arg.type.loc,
            )
            symtable.add(sym)

        ret_sym = self.create_new_local(
            funcdef.return_type,
            "@return",
            "var",
            "auto",
            funcdef.return_type.loc,
            funcdef.return_type.loc,
        )
        symtable.add(ret_sym)

        for stmt in funcdef.body:
            self.bind(stmt)

        self.pop_symtable()
        self.pop_scope()

    def bind_VarDef(self, vardef: ast.VarDef) -> None:
        varname = vardef.name.value
        varkind_optional = vardef.kind
        if varkind_optional is None:
            # bare `x: T` inside a function body - not valid in strict mode,
            # but we still need to handle it gracefully during bind; the
            # runtime/checker will reject it later.
            varkind: VarKind = "const"
            varkind_origin: VarKindOrigin = "auto"
        else:
            varkind = varkind_optional
            varkind_origin = "explicit"
        sym = self.create_new_local(
            vardef,
            varname,
            varkind,
            varkind_origin,
            vardef.loc,
            vardef.type.loc,
        )
        # XXX FIX THIS
        # Register the local in the runtime SymTable as well.
        # Skip if scope and symtable are the same object (module level).
        if self.symtable is not self.scope:
            self.symtable.add(sym)
        if vardef.value is not None:
            self.bind(vardef.value)

    # ====
    # resolve pass

    def capture_maybe(self, node: ast.Node, varname: str, use_loc: Loc) -> None:
        level, _, sym = self.lookup_ref(varname)

        if level == -1:
            # name not found, let's record a special NameError symbol
            resolved_sym = Symbol(
                varname,
                "var",
                "auto",
                "NameError",
                level=-1,
                loc=Loc.fake(),
                type_loc=Loc.fake(),
            )
            self.node_to_sym[node] = resolved_sym
            return

        elif level == 0:
            # found in the local symtable
            assert sym is not None
            if sym.is_local:
                # [decl.use-before]: does the usage happen before the declaration?
                seq = self.seq[node]
                decl_node = self.decl_node[sym]
                decl_seq = self.seq[decl_node]
                if seq < decl_seq:
                    msg = f"name `{varname}` is not defined"
                    err = SPyError("W_NameError", msg)
                    err.add("error", "used before its declaration", use_loc)
                    err.add("note", "declared later here", sym.loc)
                    raise err
            self.node_to_sym[node] = sym
            return

        else:
            # found in an outer scope: capture into the runtime symtable
            level, sym = self.lookup_definition(varname)  # type: ignore
            assert sym
            if self.symtable.lookup_maybe(varname) is None:
                new_sym = sym.replace(level=level)
                self.symtable.add(new_sym)
            if sym.impref is not None:
                self.mod_symtable.implicit_imports.add(sym.impref.modname)
            resolved_sym = self.symtable.lookup(varname)
            self.node_to_sym[node] = resolved_sym
            return

    def resolve(self, node: ast.Node) -> None:
        return node.visit("resolve", self)

    def resolve_FuncDef(self, funcdef: ast.FuncDef) -> None:
        # decorators and argument types are evaluated in the outer scope
        for decorator in funcdef.decorators:
            self.resolve(decorator)
        self.resolve(funcdef.return_type)
        for arg in funcdef.args:
            self.resolve(arg)
        for default in funcdef.defaults:
            self.resolve(default)

        # activate scope/symtable for the function and resolve its body
        scope = self.scopes[funcdef]
        symtable = self.symtables[funcdef]
        self.push_scope(scope)
        self.push_symtable(symtable)
        for stmt in funcdef.body:
            self.resolve(stmt)
        self.pop_symtable()
        self.pop_scope()

    def resolve_GlobalFuncDef(self, decl: ast.GlobalFuncDef) -> None:
        self.resolve_FuncDef(decl.funcdef)

    def resolve_Name(self, name: ast.Name) -> None:
        self.capture_maybe(name, name.id, name.loc)
