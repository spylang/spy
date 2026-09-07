from typing import Optional

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


class ScopeAnalyzer:
    """
    Visit the given AST Module and determine the scope of each name.

    See docs/src/reference/scoping.md for the full scoping rules.

    The analyzer operates in two passes:

      1. declare: find all the statements which introduce new symbols (such as
         VarDef, Assign, FuncDef, etc.). At the end of the declare() pass,
         each symtable contains all the names which are directly defined in
         that scope (i.e., sym.level == 0).

      2. flatten: for each usage of a name, determine in which scope the
         definition reside (either the current or an outer one). At the end of
         the flatten() pass, each symtable contains all the names which are
         defined or referenced in that scope.
    """

    mod: ast.Module
    stack: list[SymTable]
    inner_scopes: dict[
        ast.FuncDef | ast.GenericFuncDef | ast.ClassDef | ast.GenericClassDef, SymTable
    ]

    def __init__(self, modname: str, mod: ast.Module) -> None:
        self.mod = mod
        self.builtins_scope = SymTable.from_builtins()
        self.mod_scope = SymTable(modname, "blue", "module")
        self.stack = []
        self.inner_scopes = {}
        self.push_scope(self.builtins_scope)
        self.push_scope(self.mod_scope)

    # ===============
    # public API
    # ================

    def analyze(self) -> None:
        assert len(self.stack) == 2  # [builtins, module]
        for decl in self.mod.decls:
            self.declare(decl)
        assert len(self.stack) == 2

        for decl in self.mod.decls:
            self.flatten(decl)
        assert len(self.stack) == 2

    def by_module(self) -> SymTable:
        return self.mod_scope

    def by_funcdef(self, funcdef: ast.FuncDef) -> SymTable:
        return self.inner_scopes[funcdef]

    def by_generic_funcdef(self, gfuncdef: ast.GenericFuncDef) -> SymTable:
        return self.inner_scopes[gfuncdef]

    def by_classdef(self, classdef: ast.ClassDef) -> SymTable:
        return self.inner_scopes[classdef]

    def by_generic_classdef(self, gclassdef: ast.GenericClassDef) -> SymTable:
        return self.inner_scopes[gclassdef]

    # =====

    def new_SymTable(self, name: str, color: Color, kind: ScopeKind) -> SymTable:
        """
        Create a new SymTable whose name is derived from its parent
        """
        parent = self.stack[-1].name
        fullname = f"{parent}::{name}"
        return SymTable(fullname, color, kind)

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

    def lookup_ref(self, name: str) -> tuple[int, Optional[SymTable], Optional[Symbol]]:
        """
        Lookup a name reference, starting from the innermost scope outward.
        """
        for level, scope in enumerate(reversed(self.stack)):
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
        for level, scope in enumerate(reversed(self.stack)):
            if sym := scope.lookup_definition_maybe(name):
                return level, sym
        return -1, None

    def define_name(
        self,
        name: str,
        varkind: VarKind,
        varkind_origin: VarKindOrigin,
        loc: Loc,
        type_loc: Loc,
        *,
        impref: Optional[ImportRef] = None,
    ) -> None:
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
        ## if self.scope is self.mod_scope and varkind == "var":
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

    def capture_maybe(self, varname: str) -> None:
        level, _, _ = self.lookup_ref(varname)
        if level == -1:
            # name not found
            assert not self.scope.has_definition(varname)
            sym = Symbol(
                varname,
                "var",
                "auto",
                "NameError",
                level=-1,
                loc=Loc.fake(),
                type_loc=Loc.fake(),
            )
            self.scope.add(sym)

        elif level == 0:
            # already in this symtable, nothing to do
            return

        else:
            # found in an outer scope: capture it
            level, sym = self.lookup_definition(varname)  # type: ignore
            assert sym
            assert not self.scope.has_definition(varname)
            new_sym = sym.replace(level=level)
            self.scope.add(new_sym)
            if sym.impref is not None:
                self.mod_scope.implicit_imports.add(sym.impref.modname)

    # ====
    # declare pass

    def declare(self, node: ast.Node) -> None:
        return node.visit("declare", self)

    def declare_Import(self, imp: ast.Import) -> None:
        self.define_name(
            imp.asname,
            "const",
            "auto",
            imp.loc,
            imp.loc,
            impref=imp.ref,
        )

    def declare_GlobalFuncDef(self, decl: ast.GlobalFuncDef) -> None:
        self.declare_FuncDef(decl.funcdef)

    def declare_FuncDef(self, funcdef: ast.FuncDef) -> None:
        # declare the func name in the outer scope
        protoloc = funcdef.prototype_loc
        self.define_name(funcdef.name, "const", "funcdef", protoloc, protoloc)

        scope_color = funcdef.color
        if scope_color == "red":
            argkind: VarKind = "var"
            argkind_origin: VarKindOrigin = "red-param"
        else:
            assert False
            ## argkind = "const"
            ## argkind_origin = "blue-param"

        inner_scope = self.new_SymTable(funcdef.name, scope_color, "function")
        self.push_scope(inner_scope)
        self.inner_scopes[funcdef] = inner_scope
        for arg in funcdef.args:
            self.define_name(
                arg.name,
                argkind,
                argkind_origin,
                arg.loc,
                arg.type.loc,
            )
        self.define_name(
            "@return",
            "var",
            "auto",
            funcdef.return_type.loc,
            funcdef.return_type.loc,
        )
        for stmt in funcdef.body:
            self.declare(stmt)
        self.pop_scope()

    def declare_VarDef(self, vardef: ast.VarDef) -> None:
        varname = vardef.name.value
        varkind_optional = vardef.kind
        if varkind_optional is None:
            # bare `x: T` inside a function body — not valid in strict mode,
            # but we still need to handle it gracefully during declare; the
            # runtime/checker will reject it later.
            varkind: VarKind = "const"
            varkind_origin: VarKindOrigin = "auto"
        else:
            varkind = varkind_optional
            varkind_origin = "explicit"
        self.define_name(
            varname,
            varkind,
            varkind_origin,
            vardef.loc,
            vardef.type.loc,
        )
        if vardef.value is not None:
            self.declare(vardef.value)

    # ====
    # flatten pass

    def flatten(self, node: ast.Node) -> None:
        return node.visit("flatten", self)

    def flatten_FuncDef(self, funcdef: ast.FuncDef) -> None:
        # decorators and argument types are evaluated in the outer scope
        for decorator in funcdef.decorators:
            self.flatten(decorator)
        self.flatten(funcdef.return_type)
        for arg in funcdef.args:
            self.flatten(arg)
        for default in funcdef.defaults:
            self.flatten(default)

        # the body is evaluated in the inner scope
        inner_scope = self.by_funcdef(funcdef)
        self.push_scope(inner_scope)
        for stmt in funcdef.body:
            self.flatten(stmt)
        self.pop_scope()
        funcdef.symtable = inner_scope

    def flatten_GlobalFuncDef(self, decl: ast.GlobalFuncDef) -> None:
        self.flatten_FuncDef(decl.funcdef)

    def flatten_Name(self, name: ast.Name) -> None:
        self.capture_maybe(name.id)
