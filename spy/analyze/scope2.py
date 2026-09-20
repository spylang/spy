from typing import Optional

from spy import ast
from spy.analyze.symtable import (
    Color,
    DeclOrigin,
    ImportRef,
    Scope,
    ScopeKind,
    Symbol,
    SymTable,
    VarKind,
    VarKindOrigin,
    VarStorage,
)
from spy.errors import SPyError
from spy.location import Loc
from spy.textbuilder import ColorFormatter, TextBuilder

# SymTable and Scope are similar but conceptually different:
#
#   - `Scope` are created during the collect pass of ScopeAnalyzer, they are nested and
#     they correspond to a lexical scope (including e.g. blocks).
#
#   - `SymTable` is a runtime concept: it's a flat per-function namespace, which
#     contains its local variables

# Key used to look up Scopes in ScopeAnalyzer.scopes
# Usually a single node (ast.Module, ast.FuncDef, ...); the tuple case is for
# nodes with multiple blocks, like `(ast.If, "then")` and `(ast.If, "else")`.
ScopeKey = ast.Node | tuple[ast.Node, str]

# What a node resolves to during the bind pass: a real Symbol, or a lazy static
# error (poison) that astcompile turns into an ast.PoisonExpr.
Resolution = Symbol | SPyError


class ScopeAnalyzer:
    """
    Visit the given AST Module and determine the scope of each name.

    See docs/src/reference/scoping.md for the full scoping rules.

    The analyzer operates in two passes:

      1. collect: walk all statements that introduce new names (VarDef, FuncDef,
         Import, etc.) and add a Symbol to the current Scope.  After this pass,
         every Scope contains the names directly defined in it (sym.level == 0)
         and is read-only.

         During this pass we also create a SymTable for each FuncDef and other nodes
         with a runtime frame, and we fill it with its locals.

      2. bind: visit all nodes which need a name lookup (e.g. ast.Name), and bind
         each occurrence to the corresponding Symbol.

     Both passes maintain a stack of lexical scopes (scope_stack), one entry per
     block/function/module.  Each Scope points to the currently active `.symtable`.
    """

    mod: ast.Module
    scope_stack: list[Scope]
    scopes: dict[ScopeKey, Scope]  # which Scope corresponds to a given node?

    # == Collect and declaration sequence ==
    #
    # To detect "use before declaration", we must memoize in which order we collected
    # the nodes and when a certain declaration start to be visible: self.collect()
    # assign a monotoic "seq" number to all visited nodes, and create_new_local stores
    # the "current seq" to remember when it was created. Then later, the bind step
    # checks that the usage happens after the declaration.
    seq: dict[ast.Node, int]  # seq number for each node
    cur_seq: int
    valid_from: dict[Symbol, int]  # seq number after Sym is valid

    # A node resolves either to a Symbol or to a lazy SPyError
    _resolved_nodes: dict[ast.Node, tuple[Scope, "Resolution"]]

    def __init__(self, modname: str, mod: ast.Module) -> None:
        self.mod = mod
        self.scope_stack = []
        self.scopes = {}

        # build the [builtins, module] initial scope stack
        self.builtins_scope = Scope.from_builtins()
        mod_symtable = SymTable(modname, "blue", "module")
        mod_scope = Scope(
            modname,
            "blue",
            "module",
            symtable=mod_symtable,
            parent=self.builtins_scope,
        )

        self.scopes[mod] = mod_scope
        self.seq = {}
        self.valid_from = {}
        self.cur_seq = 0
        self._resolved_nodes = {}

    # ===============
    # public API
    # ================

    def analyze(self) -> None:
        self.push_scope(self.builtins_scope)
        self.push_scope(self.mod_scope)

        # ------- collect pass -------
        assert len(self.scope_stack) == 2  # [builtins, module]
        for decl in self.mod.decls:
            self.collect(decl)

        # ------ bind pass -----
        assert len(self.scope_stack) == 2  # [builtins, module]
        for decl in self.mod.decls:
            self.bind(decl)
        assert len(self.scope_stack) == 2

    def pp(self) -> None:
        print(self.dump(use_colors=True))

    def dump(self, *symtable_names: str, use_colors: bool = False) -> str:
        """
        Return a compact, human-readable dump of the computed symtables and the
        lexical scope nesting, including how each name resolves during the bind
        pass.

        If `symtable_names` is given, dump only the listed frames (by symtable
        name, e.g. "test::foo"); otherwise dump all of them.
        """
        b = TextBuilder(use_colors=use_colors)
        color = ColorFormatter(use_colors=use_colors)

        # Group the resolved occurrences (bind pass) by the scope they occurred in.
        # For poison (SPyError) resolutions there is no Symbol, so the display name
        # is taken from the node's source text.
        uses_by_scope: dict[str, list[tuple[str, Resolution]]] = {}
        for node, (scope, res) in self._resolved_nodes.items():
            src_name = res.src_name if isinstance(res, Symbol) else node.loc.get_src()
            uses_by_scope.setdefault(scope.name, []).append((src_name, res))

        def scope_is_empty(scope: Scope) -> bool:
            if uses_by_scope.get(scope.name):
                return False
            return all(scope_is_empty(child) for child in scope.children)

        def dump_symtable(symtable: SymTable) -> None:
            b.wl(f"symtable {symtable.name} ({symtable.kind}):")
            with b.indent():
                for slot_name, sym in symtable._symbols.items():
                    key = color.set(self._varkind_color(sym), slot_name)
                    b.wl(f"{key}: {self._fmt_sym(sym)}")

        # `frames` are the enclosing runtime frames, innermost first: frames[0] is
        # the current frame, frames[1] the parent frame, etc.  A name resolved
        # with sym.level == N lives in frames[N].
        def dump_scope(scope: Scope, frames: list[SymTable]) -> None:
            b.wl(f"scope {scope.short_name}:")
            with b.indent():
                # scope modifiers like `global x`
                for sym in scope.symbols.values():
                    if sym.storage == "decl-global":
                        b.wl(color.set("red", f"global {sym.src_name}"))
                # names USED in this scope (resolved during the bind pass)
                seen: set[str] = set()
                for src_name, res in uses_by_scope.get(scope.name, []):
                    if src_name in seen:
                        continue
                    seen.add(src_name)
                    b.wl(self._fmt_resolution(src_name, res, frames, color))
                # descend only into scopes belonging to the same runtime frame;
                # nested function scopes are dumped in their own symtable section.
                for child in scope.children:
                    if child.symtable is not scope.symtable:
                        continue
                    if child.kind == "block" and scope_is_empty(child):
                        continue
                    dump_scope(child, frames)

        # frame-owning scopes (module + FuncDefs) in collection order; block
        # scopes are dumped recursively by dump_scope, not as top-level frames.
        owners = [
            s for s in self.scopes.values() if s.kind in ("module", "function", "class")
        ]
        if symtable_names:
            owners = [s for s in owners if s.symtable.name in symtable_names]

        # for each runtime frame, dump its symtable and its lexical scopes
        for i, owner in enumerate(owners):
            if i > 0:
                b.wl()
            dump_symtable(owner.symtable)
            b.wl()
            # the frame chain, innermost first: this owner then its enclosing frames
            frames = self._enclosing_symtables(owner)
            with b.indent():
                dump_scope(owner, frames)
        return b.build()

    def _varkind_color(self, sym: Symbol) -> str:
        # match scope.py's pp_symbols: const is blue, var is red
        return "blue" if sym.varkind == "const" else "red"

    def _fmt_sym(self, sym: Symbol) -> str:
        s = f'Symbol("{sym.src_name}", "{sym.varkind}", "{sym.varkind_origin}")'
        if sym.storage == "cell":
            s += " [cell]"
        return s + self._fmt_impref(sym)

    def _fmt_resolution(
        self,
        src_name: str,
        res: "Resolution",
        frames: list[SymTable],
        color: ColorFormatter,
    ) -> str:
        if isinstance(res, SPyError):
            errname = res.etype.removeprefix("W_")
            return color.set("yellow", f"{src_name} -> {errname}")
        sym = res
        name = color.set(self._varkind_color(sym), src_name)
        if sym.level > 0:
            # the name is resolved in an outer frame: show which one, and how many
            # frame boundaries away it is
            frame = frames[sym.level]
            s = f"{name} -> {sym.slot_name} @ {frame.name} (depth={sym.level})"
        else:
            s = f"{name} -> {sym.slot_name}"
        return s + self._fmt_impref(sym)

    def _enclosing_symtables(self, scope: Scope) -> list[SymTable]:
        """
        The chain of runtime frames enclosing (and including) `scope`, innermost
        first: the scope's own frame, then its parent frame, etc.  Block scopes
        share their enclosing frame, so only function/module scopes are kept.
        """
        result = []
        s: Optional[Scope] = scope
        while s is not None:
            if s.kind in ("function", "module", "class"):
                result.append(s.symtable)
            s = s.parent
        return result

    def _fmt_impref(self, sym: Symbol) -> str:
        if sym.impref is None:
            return ""
        return f" => {sym.impref}"

    @property
    def mod_scope(self) -> Scope:
        return self.scopes[self.mod]

    @property
    def mod_symtable(self) -> SymTable:
        return self.by_module()

    def by_module(self) -> SymTable:
        return self.get_symtable(self.mod)

    def get_symtable(self, node: ast.Node) -> SymTable:
        return self.scopes[node].symtable

    def get_resolution(self, node: ast.Node) -> "Resolution":
        """
        Return what `node` resolved to: a real Symbol or a lazy poison (SPyError).
        """
        scope, res = self._resolved_nodes[node]
        return res

    def get_resolved_sym(self, node: ast.Node) -> Symbol:
        """
        Return the Symbol that `node` resolved to.
        """
        res = self.get_resolution(node)
        assert isinstance(res, Symbol)
        return res

    def get_resolved_sym_maybe(self, node: ast.Node) -> Optional[Symbol]:
        if node in self._resolved_nodes:
            scope, res = self._resolved_nodes[node]
            if isinstance(res, Symbol):
                return res
        return None

    def get_poison_error_maybe(self, node: ast.Node) -> Optional[SPyError]:
        if node in self._resolved_nodes:
            scope, res = self._resolved_nodes[node]
            if isinstance(res, SPyError):
                return res
        return None

    def bind_synthetic_node(
        self, node: ast.Node, scope: Scope, res: "Resolution"
    ) -> None:
        """
        This is exactly like set_binding, but it's a public API which can be used by
        astcompiler to bind the node it synthethizes (e.g. when desugaring a For)
        """
        self.set_binding(node, scope, res)

    def get_resolved_scope(self, node: ast.Node) -> Scope:
        """
        Return the lexical Scope in which `node` was resolved.
        """
        scope, sym = self._resolved_nodes[node]
        return scope

    # =====

    def new_Scope(
        self,
        name: str,
        color: Color,
        kind: ScopeKind,
        *,
        symtable: Optional[SymTable] = None,
    ) -> Scope:
        """
        Create a new Scope nested inside the current one.

        `symtable` is the runtime frame the scope belongs to; it defaults to the
        enclosing frame (the right choice for block scopes).  Function scopes
        pass their own freshly-created symtable.
        """
        parent = self.scope_stack[-1]
        if symtable is None:
            symtable = self.symtable
        return Scope(
            f"{parent.name}::{name}", color, kind, symtable=symtable, parent=parent
        )

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
        Return the currently active SymTable
        """
        return self.scope.symtable

    # ====
    # collect pass

    def create_new_local(
        self,
        node: ast.Node,
        name: str,
        decl_origin: DeclOrigin,
        varkind: VarKind,
        varkind_origin: VarKindOrigin,
        loc: Loc,
        type_loc: Loc,
        *,
        impref: Optional[ImportRef] = None,
        scope: Optional[Scope] = None,
        valid_from: Optional[int] = None,
    ) -> Symbol:
        """
        Add a name definition to the given scope and its symtable (level 0).

        By default, `scope` is `self.scope`. It differs only in case of implicit
        declarations which happens inside `if` blocks, which are lifted to their
        encloding scope, see [py.scope-lifting].

        `valid_from` controls when the name starts to be visible for the
        [decl.use-before] check; by default it's the current seq (the textual
        position). `valid_from=0` means "always valid", i.e. visible from the
        beginning of the scope.
        """
        if scope is None:
            scope = self.scope
        symtable = scope.symtable
        existing_sym = scope.symbols.get(name)
        if existing_sym:
            if existing_sym.storage == "decl-global":
                # rule 1: `global x` then a local decl of `x` in the same scope
                msg = f"variable `{name}` is already declared as global"
                err = SPyError("W_ScopeError", msg)
                err.add("error", "this is the new declaration", loc)
                err.add("note", f"`{name}` was declared global here", existing_sym.loc)
                raise err
            if existing_sym.storage == "decl-cannot-lift":
                # we found a decl-cannot-lift: this is not a real symbol, its only goal
                # is to prevent to place an implicit decl in this scope. We can safely
                # replace it with OUR own symbol, which will also prevent new implicit
                # decl in this scope.
                scope.remove(name)
                existing_sym = None
        if existing_sym:
            msg = f"variable `{name}` already declared"
            err = SPyError("W_ScopeError", msg)
            err.add("error", "this is the new declaration", loc)
            err.add("note", "this is the previous declaration", existing_sym.loc)
            raise err

        storage: VarStorage
        if scope.kind == "module" and varkind == "var":
            storage = "cell"
        else:
            storage = "direct"

        new_sym = Symbol(
            name,
            varkind,
            varkind_origin,
            storage,
            decl_origin=decl_origin,
            slot_name=symtable.get_fresh_slot(name),
            loc=loc,
            type_loc=type_loc,
            impref=impref,
            level=0,
        )
        scope.add(new_sym)
        symtable.add(new_sym)
        if valid_from is None:
            valid_from = self.cur_seq  # remember when it was created
        self.valid_from[new_sym] = valid_from
        return new_sym

    def collect(self, node: ast.Node) -> None:
        # like ast.Node.visit(), but keeps track of seq numbers
        self.seq[node] = self.cur_seq = len(self.seq)
        methname = f"collect_{node.__class__.__name__}"
        meth = getattr(self, methname, None)
        if meth is not None:
            meth(node)
        else:
            for child in node.get_children():
                self.collect(child)

    def collect_Import(self, imp: ast.Import) -> None:
        self.create_new_local(
            imp,
            imp.asname,
            "explicit",
            "const",
            "auto",
            imp.loc,
            imp.loc,
            impref=imp.ref,
        )

    def collect_GlobalFuncDef(self, decl: ast.GlobalFuncDef) -> None:
        self.collect_FuncDef(decl.funcdef)

    def collect_GlobalClassDef(self, decl: ast.GlobalClassDef) -> None:
        self.collect_ClassDef(decl.classdef)

    def collect_GlobalGenericFuncDef(self, decl: ast.GlobalGenericFuncDef) -> None:
        self.collect_GenericFuncDef(decl.funcdef)

    def collect_GlobalGenericClassDef(self, decl: ast.GlobalGenericClassDef) -> None:
        self.collect_GenericClassDef(decl.classdef)

    def collect_GenericFuncDef(self, gfuncdef: ast.GenericFuncDef) -> None:
        self._collect_generic(gfuncdef, gfuncdef.name, gfuncdef.args, gfuncdef.inner)

    def collect_GenericClassDef(self, gclassdef: ast.GenericClassDef) -> None:
        self._collect_generic(
            gclassdef, gclassdef.name, gclassdef.args, gclassdef.inner
        )

    def _collect_generic(
        self,
        node: ast.Node,
        name: str,
        args: list[ast.FuncArg],
        inner: ast.Stmt,
    ) -> None:
        # A GenericFuncDef/GenericClassDef is essentially a blue function:
        # def add[T](x: T, y: T) -> T:
        #     ...
        #
        # is equivalent to:
        # @blue
        # def add(T):
        #     def __impl(x: T, y: T) -> T:
        #         ...
        #     return __impl
        #
        # For scope analysis, we need to:
        #     1. collect/bind the name "add" in the outer scope
        #     2. push a scope/symtable for the blue function
        #     3. collect/bind the generic arguments ("T")
        #     4. collect/bind the inner funcdef/classdef

        # (1) collect the name of the generic function/class
        loc = inner.loc
        self.create_new_local(node, name, "explicit", "const", "funcdef", loc, loc)

        # (2) push the blue scope/symtable; see also collect_FuncDef
        symtable_name = f"{self.symtable.name}::{name}"
        symtable = SymTable(symtable_name, "blue", "function")
        inner_scope = self.new_Scope(name, "blue", "function", symtable=symtable)
        self.push_scope(inner_scope)
        self.scopes[node] = inner_scope

        # (3) collect the generic arguments
        for arg in args:
            self.create_new_local(
                arg, arg.name, "explicit", "const", "blue-param", arg.loc, arg.type.loc
            )

        # (4) collect the inner funcdef/classdef
        self.collect(inner)
        self.pop_scope()

    def collect_GlobalVarDef(self, decl: ast.GlobalVarDef) -> None:
        vardef = decl.vardef
        varname = vardef.name.value
        decl_origin: DeclOrigin = "explicit"
        if vardef.kind is None:
            # bare `x: T` at module level is an implicit const
            varkind: VarKind = "const"
            varkind_origin: VarKindOrigin = "global-const"
        else:
            varkind = vardef.kind
            varkind_origin = "explicit"

        # FIRST we collect the initializer, THEN we create the var. E.g. in:
        #     var x = x + 1
        # the "x" on the right triggers [decl.use-before]
        if vardef.value is not None:
            self.collect(vardef.value)
        self.create_new_local(
            decl,
            varname,
            decl_origin,
            varkind,
            varkind_origin,
            decl.loc,
            vardef.type.loc,
        )

    def collect_ClassDef(self, classdef: ast.ClassDef) -> None:
        # collect the class name in the outer scope. Note that the name if valid_from=0,
        # because it's an implicit forward declaration.
        self.create_new_local(
            classdef,
            classdef.name,
            "explicit",
            "const",
            "classdef",
            classdef.loc,
            classdef.loc,
            valid_from=0,
        )

        # the class body is its own frame (a "class" scope with its own symtable);
        # methods defined inside become nested funcdefs `test::P::get`.
        symtable_name = f"{self.symtable.name}::{classdef.name}"
        symtable = SymTable(symtable_name, "blue", "class")
        inner_scope = self.new_Scope(classdef.name, "blue", "class", symtable=symtable)
        self.push_scope(inner_scope)
        self.scopes[classdef] = inner_scope
        classdef.body.scope = inner_scope
        for stmt in classdef.body.body:
            self.collect(stmt)
        self.pop_scope()

    def collect_FuncDef(self, funcdef: ast.FuncDef) -> None:
        # A `def` is an implicit declaration
        protoloc = funcdef.prototype_loc
        self.assign_or_declare_maybe(funcdef, funcdef.name, "funcdef", protoloc)

        scope_color = funcdef.color
        if scope_color == "red":
            argkind: VarKind = "var"
            argkind_origin: VarKindOrigin = "red-param"
        else:
            # [py.blue-params]: blue function arguments are const.
            argkind = "const"
            argkind_origin = "blue-param"

        # the symtable name is derived from the ENCLOSING FRAME (symtable), not
        # the lexical scope: block scopes must not appear in it. E.g. a function
        # defined inside an `if` inside `foo` is `test::foo::inner`, not
        # `test::foo::if.then::inner`.
        symtable_name = f"{self.symtable.name}::{funcdef.name}"
        symtable = SymTable(symtable_name, scope_color, "function")
        inner_scope = self.new_Scope(
            funcdef.name, scope_color, "function", symtable=symtable
        )
        self.push_scope(inner_scope)
        self.scopes[funcdef] = inner_scope
        funcdef.body.scope = inner_scope

        for arg in funcdef.args:
            self.create_new_local(
                arg,
                arg.name,
                "explicit",
                argkind,
                argkind_origin,
                arg.loc,
                arg.type.loc,
            )

        ret_sym = self.create_new_local(
            funcdef.return_type,
            "@return",
            "explicit",
            "var",
            "auto",
            funcdef.return_type.loc,
            funcdef.return_type.loc,
        )

        for stmt in funcdef.body.body:
            self.collect(stmt)

        self.pop_scope()

    def collect_If(self, ifstmt: ast.If) -> None:
        self.collect(ifstmt.test)
        then_scope = self.new_Scope("if.then", self.scope.color, "block")
        self.push_scope(then_scope)
        ifstmt.then.scope = then_scope
        for stmt in ifstmt.then.body:
            self.collect(stmt)
        self.pop_scope()
        else_scope = self.new_Scope("if.else", self.scope.color, "block")
        self.push_scope(else_scope)
        ifstmt.else_.scope = else_scope
        for stmt in ifstmt.else_.body:
            self.collect(stmt)
        self.pop_scope()
        self.scopes[ifstmt, "then"] = then_scope
        self.scopes[ifstmt, "else"] = else_scope

    def collect_For(self, forstmt: ast.For) -> None:
        # The iterator (`X`) is evaluated in the enclosing scope.
        self.collect(forstmt.iter)

        # `[scope.block]`: the loop body is its own block scope.
        body_scope = self.new_Scope("for.body", self.scope.color, "block")

        # `[scope.loop-target]`: the target `i` is a block-local of the loop body.
        # `[scope.loop-target-declare]`: unless a binding of the same name already
        # exists in an enclosing scope, in which case the loop reuses it (the
        # target is an ordinary assignment) so it outlives the loop.
        self.push_scope(body_scope)
        forstmt.body.scope = body_scope
        target = forstmt.target
        res = self.scope.lookup(target.value)
        if not res.found:
            self.create_new_local(
                target,
                target.value,
                "explicit",
                "var",
                "loop-target",
                target.loc,
                forstmt.iter.loc,
            )
        for stmt in forstmt.body.body:
            self.collect(stmt)
        self.pop_scope()
        self.scopes[forstmt, "body"] = body_scope

    def collect_VarDef(self, vardef: ast.VarDef) -> None:
        varname = vardef.name.value
        decl_origin: DeclOrigin = "explicit"
        varkind_optional = vardef.kind
        if varkind_optional is None:
            # bare `x: T` inside a function body - not valid in strict mode,
            # but we still need to handle it gracefully during collect; the
            # runtime/checker will reject it later.
            varkind: VarKind = "const"
            varkind_origin: VarKindOrigin = "auto"
        else:
            varkind = varkind_optional
            varkind_origin = "explicit"

        # collect the initializer BEFORE declaring the name. E.g.:
        #     var x = x + 1
        # triggers [decl.use-before]
        if vardef.value is not None:
            self.collect(vardef.value)

        # [py.scope-lifting-mixing-error]: it is an error to mix an implicit and an
        # explicit declaration for the same name:
        #     if cond:
        #         const x = 1
        #         y = 1
        #     else:
        #         x = 2
        #         const y = 2
        #
        # In this example, "const x = 1" would shadow the implicitly lifted "x = 2", and
        # "const y = 2" would shadow the implicitly lifted "y = 1".
        #
        # To detect the mixing, we do two things:
        #   1. if the explicit decl shadows an `implicit` symbol, then it's an
        #      error. This catches the `y` case above.
        #
        #   2. if we encounter an explicit decl, we also put a `decl-cannot-lift` marker
        #      in the lift_target scope: this will cause an error if later we try to
        #      lift a symbol there. This catches the `x` case above.
        lift_target = self.get_lift_target()
        if lift_target is not self.scope:
            # we might need to do actual lifting
            sym = lift_target.symbols.get(varname)
            if sym is None:
                # (2): place the decl-cannot-lift marker in the lift_target scope
                marker = Symbol(
                    varname,
                    "const",
                    "explicit",
                    "decl-cannot-lift",
                    slot_name=varname,
                    loc=vardef.loc,
                    type_loc=vardef.type.loc,
                    level=0,
                )
                lift_target.add(marker)
            elif sym.decl_origin == "implicit":
                # (1): we detected the mixing
                self.report_mixed_declarations(varname, vardef.loc, sym.loc)

        self.create_new_local(
            vardef,
            varname,
            decl_origin,
            varkind,
            varkind_origin,
            vardef.loc,
            vardef.type.loc,
        )

    def collect_children(self, node: ast.Node) -> None:
        for child in node.get_children():
            self.collect(child)

    def collect_List(self, lst: ast.List) -> None:
        self.mod_symtable.implicit_imports.add("_list")
        self.collect_children(lst)

    def collect_Tuple(self, tup: ast.Tuple) -> None:
        self.mod_symtable.implicit_imports.add("_tuple")
        self.collect_children(tup)

    def collect_Dict(self, d: ast.Dict) -> None:
        self.mod_symtable.implicit_imports.add("_dict")
        self.collect_children(d)

    def collect_Slice(self, slc: ast.Slice) -> None:
        self.mod_symtable.implicit_imports.add("_slice")
        self.collect_children(slc)

    def collect_Assign(self, assign: ast.Assign) -> None:
        # FIRST collect the value, THEN (maybe) declare the target, like in VarDef.
        self.collect(assign.value)
        if isinstance(assign.target, ast.UnpackTarget):
            self.mod_symtable.implicit_imports.add("_tuple")
        if self.mod.scoping_rules == "pythonic":
            # [py.implicit-decl]: in pythonic_scoping, an assignment might be an
            # implicit declaration
            for tgt in assign.target.flatten():
                self.assign_or_declare_maybe(tgt, tgt.value, "auto", tgt.loc)

    def collect_AssignExpr(self, assignexpr: ast.AssignExpr) -> None:
        # [py.walrus]: a walrus `x := E` implicitly declares `x`.
        self.collect(assignexpr.value)
        if self.mod.scoping_rules == "pythonic":
            tgt = assignexpr.target
            self.assign_or_declare_maybe(tgt, tgt.value, "auto", tgt.loc)

    def get_lift_target(self) -> Scope:
        """
        [py.scope-lifting]: find the nearest lift target at or above the current
        scope.  Implicit declarations bind here.
        """
        scope = self.scope
        while not scope.is_lift_target:
            assert scope.parent is not None
            scope = scope.parent
        return scope

    def assign_or_declare_maybe(
        self,
        node: ast.Node,
        varname: str,
        varkind_origin: VarKindOrigin,
        loc: Loc,
    ) -> None:
        # Reassign an existing name, or implicitly declare
        res = self.scope.lookup(varname)
        if res.has_global_decl:
            # [global.write]: if there is `global x`, it's NOT an implicit decl
            return
        if res.found and res.level == 0:
            # the name is already present in the current frame: reassign it
            assert res.scope is not None and res.sym is not None
            if res.sym.varkind == "const" and res.sym.varkind_origin == "auto":
                # [py.constness]: a second assignment makes an implicit const a var
                self.promote_const_to_var(res.scope, res.sym)
        else:
            # first assignment: this is an implicit declaration. The declaration happens
            # in the lift_target scope, UNLESS we find an `decl-cannot-lift` marker, see
            # also collect_VarDef
            lift_target = self.get_lift_target()
            marker = lift_target.symbols.get(varname)
            if marker is not None and marker.storage == "decl-cannot-lift":
                self.report_mixed_declarations(varname, marker.loc, loc)

            self.create_new_local(
                node,
                varname,
                "implicit",
                "const",
                varkind_origin,
                loc,
                loc,
                scope=lift_target,
            )

    def report_mixed_declarations(self, name: str, exp_loc: Loc, imp_loc: Loc) -> None:
        # [py.scope-lifting-mixing-error]
        msg = f"Cannot mix implicit and explicit declarations for `{name}`"
        err = SPyError("W_ScopeError", msg)
        err.add("error", f"this is an explicit declaration", exp_loc)
        err.add("error", f"this is an implicit declaration", imp_loc)
        raise err

    def promote_const_to_var(self, scope: Scope, sym: Symbol) -> None:
        # `scope` is the scope that owns `sym` (may be an outer block for a lifted
        # binding, not necessarily self.scope).
        assert sym.varkind == "const"
        new_sym = sym.replace(varkind="var")
        scope.symbols[sym.src_name] = new_sym
        scope.symtable._symbols[sym.slot_name] = new_sym
        self.valid_from[new_sym] = self.valid_from.pop(sym)

    def collect_AugAssign(self, node: ast.AugAssign) -> None:
        # [py.augassign]: an AugAssign does NOT implicitly declare, but counts as a
        # re-assignment
        if self.mod.scoping_rules == "pythonic":
            res = self.scope.lookup(node.target.value)
            if (
                res.found
                and res.sym is not None
                and res.scope is not None
                and res.sym.varkind == "const"
                and res.sym.varkind_origin == "auto"
            ):
                self.promote_const_to_var(res.scope, res.sym)
        self.collect(node.value)

    def collect_Global(self, glob: ast.Global) -> None:
        # [global.write]: record that we saw a `global x`. See Scope.lookup.
        for name in glob.names:
            existing = self.scope.symbols.get(name)
            if existing is not None:
                # a `global x` cannot coexist with a local `x` in the same scope
                msg = f"variable `{name}` is already declared"
                err = SPyError("W_ScopeError", msg)
                err.add("error", "this is the new declaration", glob.loc)
                err.add("note", "this is the previous declaration", existing.loc)
                raise err
            marker = Symbol(
                name,
                "var",
                "explicit",
                "decl-global",
                slot_name=name,
                loc=glob.loc,
                type_loc=glob.loc,
                level=0,
            )
            self.scope.add(marker)

    # ====
    # bind pass

    def set_binding(self, node: ast.Node, scope: Scope, res: "Resolution") -> None:
        self._resolved_nodes[node] = (scope, res)

    def find_loop_target_maybe(self, varname: str) -> Optional[Symbol]:
        """
        Find a loop-target Symbol named `varname` in the current frame, if any.
        """
        for sym in self.symtable._symbols.values():
            if sym.src_name == varname and sym.varkind_origin == "loop-target":
                return sym
        return None

    def make_NameError(self, varname: str, use_loc: Loc) -> SPyError:
        err = SPyError("W_NameError", f"name `{varname}` is not defined")
        err.add("error", "not found in this scope", use_loc)
        # [scope.loop-target]: if `varname` is local to a `for` body in this frame,
        # teach the user how to make it outlive the loop.
        if (sym := self.find_loop_target_maybe(varname)) is not None:
            msg = f"help: declare `var {varname}: auto` before the loop"
            err.add("note", msg, sym.loc)
        return err

    def lookup_and_bind(self, node: ast.Node, varname: str, use_loc: Loc) -> None:
        # NOTE: a not-found / used-before name resolves to a lazy SPyError (stored
        # in _resolved_nodes); astcompile turns it into an ast.PoisonExpr.

        res = self.scope.lookup(varname)
        level, sym = res.level, res.sym

        if not res.found:
            # name not found: the node resolves to a lazy NameError (no Symbol)
            self.set_binding(node, self.scope, self.make_NameError(varname, use_loc))
            return

        elif level == 0:
            # found in the local symtable
            assert sym is not None
            if sym.is_local and node in self.seq:
                seq = self.seq[node]
                if seq < self.valid_from[sym]:
                    # [decl.use-before]: the use happens before the name becomes valid;
                    # the node resolves to a lazy error (no usable Symbol here)
                    err = SPyError("W_NameError", f"name `{varname}` is not defined")
                    err.add("error", "used before its declaration", use_loc)
                    err.add("note", "declared later here", sym.loc)
                    # a common cause is a bare assignment `x = ...` which implicitly
                    # declares a local that shadows a module-level global; hint at it.
                    glob = self.mod_scope.symbols.get(varname)
                    if glob is not None and glob is not sym:
                        err.add("note", f"help: shadowing this `{varname}`", glob.loc)
                        msg = f"help: add `global {varname}` earlier"
                        err.add("note", msg, use_loc)
                    self.set_binding(node, self.scope, err)
                    return

            self.set_binding(node, self.scope, sym)
            return

        else:
            # found in an outer scope
            assert sym is not None
            if sym.impref is not None:
                self.mod_symtable.implicit_imports.add(sym.impref.modname)
            self.set_binding(node, self.scope, sym.replace(level=level))
            return

    def lookup_and_bind_target(
        self, node: ast.Node, varname: str, use_loc: Loc
    ) -> None:
        """
        Bind an assignment target.

        Like lookup_and_bind, but a target that resolves to a module-level binding is
        rejected unless there is an explicit `global` declaration [global.write]
        """
        res = self.scope.lookup(varname)
        sym = res.sym
        if (
            res.level > 0
            and res.scope is not None
            and res.scope.kind == "module"
            and not res.has_global_decl
        ):
            assert sym is not None
            msg = f"`{varname}` cannot be re-assigned without a `global` declaration"
            err = SPyError("W_ScopeError", msg)
            err.add("error", f"`{varname}` is a global", use_loc)
            err.add("note", f"help: add `global {varname}` earlier", use_loc)
            err.add("note", f"`{varname}` is declared here", sym.loc)
            self.set_binding(node, self.scope, err)
            return
        self.lookup_and_bind(node, varname, use_loc)

    def bind(self, node: ast.Node) -> None:
        return node.visit("bind", self)

    def bind_FuncDef(self, funcdef: ast.FuncDef) -> None:
        # NOTE: evaluate arg.type in the OUTER scope, arg in the INNER scope.
        #
        # The funcdef NAME is bound to the outer scope.
        self.lookup_and_bind(funcdef, funcdef.name, funcdef.prototype_loc)

        # outer scope: decorators and argument types
        for decorator in funcdef.decorators:
            self.bind(decorator)
        self.bind(funcdef.return_type)
        for arg in funcdef.args:
            self.bind(arg.type)
        for default in funcdef.defaults:
            self.bind(default)

        # inner scope: arguments and function body
        scope = self.scopes[funcdef]
        self.push_scope(scope)
        for arg in funcdef.args:
            self.lookup_and_bind(arg, arg.name, arg.loc)
        for stmt in funcdef.body.body:
            self.bind(stmt)
        self.pop_scope()

    def bind_GlobalFuncDef(self, decl: ast.GlobalFuncDef) -> None:
        self.bind_FuncDef(decl.funcdef)

    def bind_GlobalClassDef(self, decl: ast.GlobalClassDef) -> None:
        self.bind_ClassDef(decl.classdef)

    def bind_ClassDef(self, classdef: ast.ClassDef) -> None:
        # the classdef NAME is bound in the outer scope, the body in the inner scope
        self.lookup_and_bind(classdef, classdef.name, classdef.loc)
        scope = self.scopes[classdef]
        self.push_scope(scope)
        for stmt in classdef.body.body:
            self.bind(stmt)
        self.pop_scope()

    def bind_GlobalGenericFuncDef(self, decl: ast.GlobalGenericFuncDef) -> None:
        self.bind_GenericFuncDef(decl.funcdef)

    def bind_GlobalGenericClassDef(self, decl: ast.GlobalGenericClassDef) -> None:
        self.bind_GenericClassDef(decl.classdef)

    def bind_GenericFuncDef(self, gfuncdef: ast.GenericFuncDef) -> None:
        self._bind_generic(gfuncdef, gfuncdef.name, gfuncdef.args, gfuncdef.inner)

    def bind_GenericClassDef(self, gclassdef: ast.GenericClassDef) -> None:
        self._bind_generic(gclassdef, gclassdef.name, gclassdef.args, gclassdef.inner)

    def _bind_generic(
        self,
        node: ast.Node,
        name: str,
        args: list[ast.FuncArg],
        inner: ast.Stmt,
    ) -> None:
        # See the big comment in _collect_generic for a general overview of the steps

        # (1) bind the name of the generic in the outer scope
        self.lookup_and_bind(node, name, inner.loc)

        # bind arg types (still in the outer scope)
        for arg in args:
            self.bind(arg.type)

        # (2) push a scope for the blue function
        scope = self.scopes[node]
        self.push_scope(scope)
        for arg in args:
            # (3) bind the generic arguments ("T")
            self.lookup_and_bind(arg, arg.name, arg.loc)

        # (4) bind the inner funcdef/classdef
        self.bind(inner)
        self.pop_scope()

    def bind_If(self, ifstmt: ast.If) -> None:
        self.bind(ifstmt.test)
        then_scope = self.scopes[ifstmt, "then"]
        self.push_scope(then_scope)
        for stmt in ifstmt.then.body:
            self.bind(stmt)
        self.pop_scope()
        else_scope = self.scopes[ifstmt, "else"]
        self.push_scope(else_scope)
        for stmt in ifstmt.else_.body:
            self.bind(stmt)
        self.pop_scope()

    def bind_For(self, forstmt: ast.For) -> None:
        self.bind(forstmt.iter)
        body_scope = self.scopes[forstmt, "body"]
        self.push_scope(body_scope)
        tgt = forstmt.target
        self.lookup_and_bind(tgt, tgt.value, tgt.loc)
        for stmt in forstmt.body.body:
            self.bind(stmt)
        self.pop_scope()

    def bind_VarDef(self, vardef: ast.VarDef) -> None:
        # a VarDef must have a local symbol in the current scope, get it
        sym = self.scope.symbols[vardef.name.value]
        assert sym.level == 0
        self.set_binding(vardef, self.scope, sym)
        self.bind(vardef.type)
        if vardef.value is not None:
            self.bind(vardef.value)

    def bind_Assign(self, assign: ast.Assign) -> None:
        self.bind(assign.value)
        for tgt in assign.target.flatten():
            self.lookup_and_bind_target(tgt, tgt.value, tgt.loc)

    def bind_AugAssign(self, node: ast.AugAssign) -> None:
        # [py.augassign]: the target is both read and written
        self.bind(node.value)
        tgt = node.target
        self.lookup_and_bind_target(tgt, tgt.value, tgt.loc)

    def bind_AssignExpr(self, assignexpr: ast.AssignExpr) -> None:
        # walrus `x := E`
        self.bind(assignexpr.value)
        tgt = assignexpr.target
        self.lookup_and_bind_target(tgt, tgt.value, tgt.loc)

    def bind_Name(self, name: ast.Name) -> None:
        self.lookup_and_bind(name, name.id, name.loc)
