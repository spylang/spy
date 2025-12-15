# ================== IMPORTANT: .spyc versioning =================
# Update importing.SPYC_VERSION in case of any significant change
# ================================================================

from typing import TYPE_CHECKING, Optional

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

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


class ScopeAnalyzer:
    """
    Visit the given AST Module and determine the scope of each name.

    The scoping rules for SPy are very simple for now:

      - names defined at module-level scopes are always available to all
        their inner scopes

      - inside a function, assigment defines a local variable ONLY if this
        name does not exist in an outer scope. Note that this is different
        from Python rules. No more 'global' and 'nonlocal' declarations.

      - shadowing a name is an error

    In the future, we might want to introduce a special compatibility mode to
    use Python's rules to make porting easier, e.g. by using `from __python__
    import scoping_rules`, but for now it's not a priority.

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

    vm: "SPyVM"
    mod: ast.Module
    stack: list[SymTable]
    inner_scopes: dict[ast.FuncDef | ast.ClassDef, SymTable]
    loop_depth: int

    def __init__(self, vm: "SPyVM", modname: str, mod: ast.Module) -> None:
        self.vm = vm
        self.mod = mod
        self.builtins_scope = SymTable.from_builtins(vm)
        self.mod_scope = SymTable(modname, "blue", "module")
        self.stack = []
        self.inner_scopes = {}
        self.loop_depth = 0
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

    def by_classdef(self, classdef: ast.ClassDef) -> SymTable:
        return self.inner_scopes[classdef]

    def pp(self) -> None:
        print("Implicit imports:")
        for modname in self.mod_scope.implicit_imports:
            print(f"    {modname}")
        print()
        self.by_module().pp()
        print()
        for key, symtable in self.inner_scopes.items():
            symtable.pp()
            print()

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
        Lookup a name reference, starting from the innermost scope,
        towards the outer.
        """
        for level, scope in enumerate(reversed(self.stack)):
            if sym := scope.lookup_maybe(name):
                return level, scope, sym
        # not found
        return -1, None, None

    def lookup_definition(self, name: str) -> tuple[int, Optional[Symbol]]:
        """
        Lookup a name definition, starting from the innermost scope,
        towards the output.
        """
        for level, scope in enumerate(reversed(self.stack)):
            if sym := scope.lookup_definition_maybe(name):
                return level, sym
        # not found
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
        Add a name definition to the current scope.

        The level of the new symbol will be 0.
        """
        level, scope, sym = self.lookup_ref(name)
        if sym and name != "@return":
            assert scope is not None
            if level == 0 and scope.color == "blue":
                # this happens if we have e.g. the same name defined in two
                # branches of an "if".
                # Note that if the redeclaration happens at runtime, it's
                # still an error, but it's caught by astframe.
                return

            elif level == 0:
                # re-declaration in the same scope
                msg = f"variable `{name}` already declared"
                err = SPyError("W_ScopeError", msg)
                err.add("error", "this is the new declaration", loc)
                err.add("note", "this is the previous declaration", sym.loc)
                raise err

            elif scope is not self.builtins_scope:
                # shadowing a name in an outer scope
                # Exception: always allow shadowing builtins
                msg = (
                    f"variable `{name}` shadows a name declared " + "in an outer scope"
                )
                err = SPyError("W_ScopeError", msg)
                err.add("error", "this is the new declaration", loc)
                err.add("note", "this is the previous declaration", sym.loc)
                raise err

        # Determine storage type: module-level vars use "cell", others use
        # "direct"
        assert varkind is not None
        storage: VarStorage
        if self.scope is self.mod_scope and varkind == "var":
            storage = "cell"
        else:
            storage = "direct"

        sym = Symbol(
            name,
            varkind,
            varkind_origin,
            storage,
            loc=loc,
            type_loc=type_loc,
            impref=impref,
            level=0,
        )
        self.scope.add(sym)

    # ====

    def declare(self, node: ast.Node) -> None:
        """
        Visit all the nodes which introduce a new name in the scope, and
        add symbol definitions to the corresponding symtable.
        """
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

    def declare_GlobalVarDef(self, decl: ast.GlobalVarDef) -> None:
        varname = decl.vardef.name.value
        varkind = decl.vardef.kind
        if varkind is None:
            varkind = "const"
            varkind_origin: VarKindOrigin = "global-const"
        else:
            varkind_origin = "explicit"
        self.define_name(
            varname,
            varkind,
            varkind_origin,
            decl.loc,
            decl.vardef.type.loc,
        )

    def declare_VarDef(self, vardef: ast.VarDef) -> None:
        varname = vardef.name.value
        varkind = vardef.kind
        if varkind is None:
            if self.loop_depth > 0:
                varkind = "var"
            else:
                varkind = "const"
            varkind_origin: VarKindOrigin = "auto"
        else:
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

    def declare_FuncDef(self, funcdef: ast.FuncDef) -> None:
        # declare the func in the "outer" scope
        protoloc = funcdef.prototype_loc
        self.define_name(funcdef.name, "const", "funcdef", protoloc, protoloc)
        # add function arguments to the "inner" scope
        scope_color = funcdef.color
        if scope_color == "red":
            argkind: VarKind = "var"
            argkind_origin: VarKindOrigin = "red-param"
        else:
            argkind = "const"
            argkind_origin = "blue-param"

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

    def declare_ClassDef(self, classdef: ast.ClassDef) -> None:
        # declare the class in the "outer" scope
        self.define_name(
            classdef.name,
            "const",
            "classdef",
            classdef.loc,
            classdef.loc,
        )
        inner_scope = self.new_SymTable(classdef.name, "blue", "class")
        self.push_scope(inner_scope)
        self.inner_scopes[classdef] = inner_scope
        for vardef in classdef.fields:
            # Class fields are always "var" with origin "class-field"
            self.define_name(
                vardef.name.value,
                "var",
                "class-field",
                vardef.loc,
                vardef.type.loc,
            )
        for stmt in classdef.body:
            self.declare(stmt)
        self.pop_scope()

    def declare_Assign(self, assign: ast.Assign) -> None:
        self._declare_target_maybe(assign.target, assign.value)
        self.declare(assign.value)

    def declare_AugAssign(self, augassign: ast.AugAssign) -> None:
        self._promote_const_to_var_maybe(augassign.target)
        self.declare(augassign.value)

    def declare_UnpackAssign(self, unpack: ast.UnpackAssign) -> None:
        for target in unpack.targets:
            self._declare_target_maybe(target, unpack.value)
        self.declare(unpack.value)

    def declare_AssignExpr(self, assignexpr: ast.AssignExpr) -> None:
        self._declare_target_maybe(assignexpr.target, assignexpr.value)
        self.declare(assignexpr.value)

    def _declare_target_maybe(self, target: ast.StrConst, value: ast.Expr) -> None:
        # if target name does not exist elsewhere, we treat it as an implicit
        # declaration
        level, scope, sym = self.lookup_ref(target.value)
        if sym is None:
            # First assignment: mark as const unless in a loop
            type_loc = value.loc
            if self.loop_depth > 0:
                varkind: VarKind = "var"
            else:
                varkind = "const"
            self.define_name(target.value, varkind, "auto", target.loc, type_loc)
        else:
            # possible second assignment: promote to var if needed
            self._promote_const_to_var_maybe(target)

    def _promote_const_to_var_maybe(self, target: ast.StrConst) -> None:
        level, scope, sym = self.lookup_ref(target.value)
        if (
            sym
            and sym.is_local
            and sym.varkind == "const"
            and sym.varkind_origin == "auto"
        ):
            if target.value in self.scope._symbols:
                # Second assignment to a local const: make it var
                old_sym = self.scope._symbols[target.value]
                if old_sym.varkind == "const":
                    new_sym = old_sym.replace(varkind="var")
                    self.scope._symbols[target.value] = new_sym

    def declare_While(self, whilestmt: ast.While) -> None:
        # Increment loop depth before processing body
        self.loop_depth += 1
        self.declare(whilestmt.test)
        for stmt in whilestmt.body:
            self.declare(stmt)
        self.loop_depth -= 1

    def declare_For(self, forstmt: ast.For) -> None:
        # Declare the hidden iterator variable _$iter0
        iter_name = f"_$iter{forstmt.seq}"
        self.define_name(
            iter_name,
            "var",
            "auto",
            forstmt.iter.loc,
            forstmt.iter.loc,
        )

        # Declare the loop variable (e.g., "i" in "for i in range(10)")
        # What is the "type_loc" of i? It's an implicit declaration, and its
        # value depends on the iterator returned by range. So we use
        # "range(10)" as the type_loc.
        self.define_name(
            forstmt.target.value,
            "var",
            "auto",
            forstmt.target.loc,
            forstmt.iter.loc,
        )

        # Increment loop depth before processing body
        self.loop_depth += 1
        self.declare(forstmt.iter)
        for stmt in forstmt.body:
            self.declare(stmt)
        self.loop_depth -= 1

    # ===

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
            # name already in the symtable, nothing to do
            return

        else:
            # the name was found but in an outer scope. Let's "capture" it.
            level, sym = self.lookup_definition(varname)  # type: ignore
            assert sym
            assert not self.scope.has_definition(varname)
            new_sym = sym.replace(level=level)
            self.scope.add(new_sym)
            if sym.impref is not None:
                self.mod_scope.implicit_imports.add(sym.impref.modname)

    def flatten(self, node: ast.Node) -> None:
        """
        Visit all the nodes in the AST and flatten the symtables of all the
        FuncDefs.

        In particular, introduce a symbol for every Name which is used inside
        a function but defined in some outer scope.
        """
        return node.visit("flatten", self)

    def flatten_FuncDef(self, funcdef: ast.FuncDef) -> None:
        # decorators are evaluated in the outer scope
        for decorator in funcdef.decorators:
            self.flatten(decorator)
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

    def flatten_ClassDef(self, classdef: ast.ClassDef) -> None:
        inner_scope = self.by_classdef(classdef)
        self.push_scope(inner_scope)
        for vardef in classdef.fields:
            self.flatten(vardef)
        for stmt in classdef.body:
            self.flatten(stmt)
        self.pop_scope()
        #
        classdef.symtable = inner_scope

    def flatten_Name(self, name: ast.Name) -> None:
        self.capture_maybe(name.id)

    def flatten_Assign(self, assign: ast.Assign) -> None:
        self.capture_maybe(assign.target.value)
        self.flatten(assign.value)

    def flatten_AssignExpr(self, assignexpr: ast.AssignExpr) -> None:
        self.capture_maybe(assignexpr.target.value)
        self.flatten(assignexpr.value)

    def flatten_For(self, forstmt: ast.For) -> None:
        # capture the loop variable and flatten the iterator
        self.capture_maybe(forstmt.target.value)
        self.flatten(forstmt.iter)
        # flatten the body
        for stmt in forstmt.body:
            self.flatten(stmt)

    def flatten_List(self, lst: ast.List) -> None:
        self.mod_scope.implicit_imports.add("_list")
        for item in lst.items:
            self.flatten(item)
