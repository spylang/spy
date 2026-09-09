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


class ScopeAnalyzer:
    """
    Visit the given AST Module and determine the scope of each name.

    See docs/src/reference/scoping.md for the full scoping rules.

    The analyzer operates in two passes:

      1. bind: walk all statements that introduce new names (VarDef, FuncDef,
         Import, etc.) and add a Symbol to the current Scope.  After this pass,
         every Scope contains the names directly defined in it (sym.level == 0)
         and is read-only.

      2. resolve: find the right Symbol associated to each node which needs a name
         lookup (e.g. ast.Name), and fill node_to_sym.  Moreover, create a flat SymTable
         for each FuncDef: walk all name uses and, for each one, find which Scope
         contains the definition.  Two separate stacks are maintained:

         - scope_stack: the lexical Scope stack, by re-pushing the Scopes created during
           bind (and stored inside inner_scope)

         - symtable_stack: the runtime SymTable stack.  A fresh SymTable is pushed for
           each FuncDef.  Every node which needs to do a name lookup finds a symbol in
           the scope_stack and captures it into the current symtable.
    """

    mod: ast.Module

    scope_stack: list[Scope]
    symtable_stack: list[SymTable]

    # which scope corresponds to each block?
    scopes: dict[
        ast.FuncDef | ast.GenericFuncDef | ast.ClassDef | ast.GenericClassDef, Scope
    ]

    # which symtable corresponds to each FuncDef & friends?
    symtables: dict[
        ast.FuncDef | ast.GenericFuncDef | ast.ClassDef | ast.GenericClassDef, SymTable
    ]

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

        # ------- bind pass -------
        assert len(self.scope_stack) == 2  # [builtins, module]
        for decl in self.mod.decls:
            self.bind(decl)

        # ------ resolve pass -----
        assert len(self.scope_stack) == 2  # [builtins, module]
        self.symtable_stack.append(self.mod_symtable)
        for decl in self.mod.decls:
            self.resolve(decl)
        self.symtable_stack.pop()
        assert len(self.symtable_stack) == 0
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

    @property
    def scope(self) -> Scope:
        """
        Return the currently active lexical scope.
        """
        return self.scope_stack[-1]

    @property
    def symtable(self) -> SymTable:
        """
        Return the current runtime SymTable (write target during resolve).
        """
        return self.symtable_stack[-1]

    def lookup_ref(self, name: str) -> tuple[int, Optional[Scope], Optional[Symbol]]:
        """
        Lookup a name reference, starting from the innermost scope outward.
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

    def define_name(
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
        Add a name definition to the current scope (level 0).
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

    def capture_maybe(self, node: ast.Node, varname: str, use_loc: Loc) -> None:
        level, _, sym = self.lookup_ref(varname)
        # All writes (NameErrors, outer-scope captures) go to self.symtable,
        # the current runtime SymTable.
        if level == -1:
            # name not found
            if self.symtable.lookup_maybe(varname) is None:
                new_sym = Symbol(
                    varname,
                    "var",
                    "auto",
                    "NameError",
                    level=-1,
                    loc=Loc.fake(),
                    type_loc=Loc.fake(),
                )
                self.symtable.add(new_sym)
            resolved_sym = self.symtable.lookup(varname)

        elif level == 0:
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
            resolved_sym = sym

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

    # ====
    # bind pass

    def bind(self, node: ast.Node) -> None:
        return node.visit("bind", self)

    def bind_Import(self, imp: ast.Import) -> None:
        self.define_name(
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
        self.define_name(funcdef, funcdef.name, "const", "funcdef", protoloc, protoloc)

        scope_color = funcdef.color
        if scope_color == "red":
            argkind: VarKind = "var"
            argkind_origin: VarKindOrigin = "red-param"
        else:
            assert False
            ## argkind = "const"
            ## argkind_origin = "blue-param"

        inner_scope = self.new_Scope(funcdef.name, scope_color, "function")
        self.push_scope(inner_scope)
        self.scopes[funcdef] = inner_scope
        for arg in funcdef.args:
            self.define_name(
                arg,
                arg.name,
                argkind,
                argkind_origin,
                arg.loc,
                arg.type.loc,
            )
        self.define_name(
            funcdef.return_type,
            "@return",
            "var",
            "auto",
            funcdef.return_type.loc,
            funcdef.return_type.loc,
        )
        for stmt in funcdef.body:
            self.bind(stmt)
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
        self.define_name(
            vardef,
            varname,
            varkind,
            varkind_origin,
            vardef.loc,
            vardef.type.loc,
        )
        if vardef.value is not None:
            self.bind(vardef.value)

    # ====
    # resolve pass

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

        # Build a fresh runtime SymTable for this function, pre-populated with
        # the args and @return from the bind-pass Scope.
        bind_scope = self.scopes[funcdef]
        symtable = SymTable(bind_scope.name, bind_scope.color, bind_scope.kind)
        for sym in bind_scope._symbols.values():
            symtable.add(sym)
        self.symtables[funcdef] = symtable

        # Push the bind-pass Scope for name resolution and the fresh SymTable
        # as the write target.
        self.push_scope(bind_scope)
        self.symtable_stack.append(symtable)
        for stmt in funcdef.body:
            self.resolve(stmt)
        self.symtable_stack.pop()
        self.pop_scope()

    def resolve_GlobalFuncDef(self, decl: ast.GlobalFuncDef) -> None:
        self.resolve_FuncDef(decl.funcdef)

    def resolve_Name(self, name: ast.Name) -> None:
        self.capture_maybe(name, name.id, name.loc)
