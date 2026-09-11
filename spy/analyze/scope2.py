from typing import Optional

from spy import ast
from spy.analyze.symtable import (
    Color,
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
    decl_node: dict[Symbol, ast.Node]  # which node declared a given Symbol?
    seq: dict[ast.Node, int]  # unique seq ID of every node (used by [decl.use-before])
    # A node resolves either to a Symbol or to a lazy SPyError
    _resolved_nodes: dict[ast.Node, tuple[Scope, "Resolution"]]

    def __init__(self, modname: str, mod: ast.Module) -> None:
        self.mod = mod
        self.scope_stack = []
        self.scopes = {}

        # build the [builtins, module] initial scope stack
        self.builtins_scope = Scope.from_builtins()
        mod_symtable = SymTable(modname, "blue", "module")
        mod_symtable.scoping_rules = "strict"  # KILL ME
        mod_scope = Scope(
            modname,
            "blue",
            "module",
            symtable=mod_symtable,
            parent=self.builtins_scope,
        )

        self.scopes[mod] = mod_scope
        self.seq = {node: i for i, node in enumerate(mod.walk())}
        self.decl_node = {}
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
        owners = [s for s in self.scopes.values() if s.kind in ("module", "function")]
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
            if s.kind in ("function", "module"):
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

    def get_resolved_sym(self, node: ast.Node) -> Symbol:
        """
        Return the Symbol that `node` resolved to.
        """
        scope, res = self._resolved_nodes[node]
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

    def bind_synthetic_node(self, node: ast.Node, scope: Scope, sym: Symbol) -> None:
        """
        This is exactly like set_binding, but it's a public API which can be used by
        astcompiler to bind the node it synthethizes (e.g. when desugaring a For)
        """
        self.set_binding(node, scope, sym)

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

    def lookup_name_in_scopes(
        self, name: str
    ) -> tuple[int, Optional[Scope], Optional[Symbol]]:
        """
        Lookup a name in the scope_stack, starting from the innermost scope outward.

        Return the level (frame depth): the number of symtable (function/module)
        boundaries crossed to reach the defining scope.  Level 0 means the current
        frame; level 1 means one frame up; etc.
        """
        frame_depth = 0
        seen_own_frame = False
        for scope in reversed(self.scope_stack):
            ## if scope.kind == "class":
            ##     # jump over 'class' scopes
            ##     continue
            if scope.kind in ("function", "module"):
                if seen_own_frame:
                    # crossing out of an enclosing frame: one more hop
                    frame_depth += 1
                else:
                    # this is the frame we started in (innermost function/module);
                    # block scopes below it don't count as hops
                    seen_own_frame = True
            if sym := scope.lookup_maybe(name):
                return frame_depth, scope, sym
        return -1, None, None

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
        existing_sym = self.scope.lookup_maybe(name)
        if existing_sym:
            msg = f"variable `{name}` already declared"
            err = SPyError("W_ScopeError", msg)
            err.add("error", "this is the new declaration", loc)
            err.add("note", "this is the previous declaration", existing_sym.loc)
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
            slot_name=self.symtable.get_fresh_slot(name),
            loc=loc,
            type_loc=type_loc,
            impref=impref,
            level=0,
        )
        self.scope.add(new_sym)
        self.symtable.add(new_sym)
        self.decl_node[new_sym] = node
        return new_sym

    def collect(self, node: ast.Node) -> None:
        return node.visit("collect", self)

    def collect_Import(self, imp: ast.Import) -> None:
        self.create_new_local(
            imp,
            imp.asname,
            "const",
            "auto",
            imp.loc,
            imp.loc,
            impref=imp.ref,
        )

    def collect_GlobalFuncDef(self, decl: ast.GlobalFuncDef) -> None:
        self.collect_FuncDef(decl.funcdef)

    def collect_FuncDef(self, funcdef: ast.FuncDef) -> None:
        # collect the func name in the outer scope
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

        # the symtable name is derived from the ENCLOSING FRAME (symtable), not
        # the lexical scope: block scopes must not appear in it. E.g. a function
        # defined inside an `if` inside `foo` is `test::foo::inner`, not
        # `test::foo::if.then::inner`.
        symtable_name = f"{self.symtable.name}::{funcdef.name}"
        symtable = SymTable(symtable_name, scope_color, "function")
        symtable.scoping_rules = "strict"  # KILL ME
        inner_scope = self.new_Scope(
            funcdef.name, scope_color, "function", symtable=symtable
        )
        self.push_scope(inner_scope)
        self.scopes[funcdef] = inner_scope

        for arg in funcdef.args:
            self.create_new_local(
                arg,
                arg.name,
                argkind,
                argkind_origin,
                arg.loc,
                arg.type.loc,
            )

        ret_sym = self.create_new_local(
            funcdef.return_type,
            "@return",
            "var",
            "auto",
            funcdef.return_type.loc,
            funcdef.return_type.loc,
        )

        for stmt in funcdef.body:
            self.collect(stmt)

        self.pop_scope()

    def collect_If(self, ifstmt: ast.If) -> None:
        self.collect(ifstmt.test)
        then_scope = self.new_Scope("if.then", self.scope.color, "block")
        self.push_scope(then_scope)
        for stmt in ifstmt.then_body:
            self.collect(stmt)
        self.pop_scope()
        else_scope = self.new_Scope("if.else", self.scope.color, "block")
        self.push_scope(else_scope)
        for stmt in ifstmt.else_body:
            self.collect(stmt)
        self.pop_scope()
        self.scopes[ifstmt, "then"] = then_scope
        self.scopes[ifstmt, "else"] = else_scope

    def collect_For(self, forstmt: ast.For) -> None:
        # ASTCompiler desugars:
        #   for i in X:
        #       body
        # into:
        #   $_iter = X.__fastiter__()
        #   while $_iter.__continue_iteration__():
        #       i = $_iter.__item__()
        #       $_iter = $_iter.__next__()
        #       body
        #
        # Note that there is a hidden $_iter variable. We bind it to the For node.

        # The iterator (`X`) is evaluated in the enclosing scope.
        self.collect(forstmt.iter)

        # `[scope.block]`: the loop body is its own block scope.
        body_scope = self.new_Scope("for.body", self.scope.color, "block")

        iter_loc = forstmt.iter.loc
        self.create_new_local(forstmt, "_$iter", "var", "auto", iter_loc, iter_loc)

        # `[scope.loop-target]`: the target `i` is a block-local of the loop body.
        # `[scope.loop-target-declare]`: unless a binding of the same name already
        # exists in an enclosing scope, in which case the loop reuses it (the
        # target is an ordinary assignment) so it outlives the loop.
        self.push_scope(body_scope)
        target = forstmt.target
        level, _, _ = self.lookup_name_in_scopes(target.value)
        if level == -1:
            self.create_new_local(
                target,
                target.value,
                "var",
                "loop-target",
                target.loc,
                forstmt.iter.loc,
            )
        for stmt in forstmt.body:
            self.collect(stmt)
        self.pop_scope()
        self.scopes[forstmt, "body"] = body_scope

    def collect_VarDef(self, vardef: ast.VarDef) -> None:
        varname = vardef.name.value
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
        sym = self.create_new_local(
            vardef,
            varname,
            varkind,
            varkind_origin,
            vardef.loc,
            vardef.type.loc,
        )
        if vardef.value is not None:
            self.collect(vardef.value)

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

        level, _, sym = self.lookup_name_in_scopes(varname)

        if level == -1:
            # name not found: the node resolves to a lazy NameError (no Symbol)
            self.set_binding(node, self.scope, self.make_NameError(varname, use_loc))
            return

        elif level == 0:
            # found in the local symtable
            assert sym is not None
            if sym.is_local:
                seq = self.seq[node]
                decl_node = self.decl_node[sym]
                decl_seq = self.seq[decl_node]
                if seq < decl_seq:
                    # [decl.use-before]: the use happens before the declaration;
                    # the node resolves to a lazy error (no usable Symbol here)
                    err = SPyError("W_NameError", f"name `{varname}` is not defined")
                    err.add("error", "used before its declaration", use_loc)
                    err.add("note", "declared later here", sym.loc)
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

    def bind(self, node: ast.Node) -> None:
        return node.visit("bind", self)

    def bind_FuncDef(self, funcdef: ast.FuncDef) -> None:
        # NOTE: arg.type is evaluated in the OUTER scope, while arg in the INNER scope
        #
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
        for stmt in funcdef.body:
            self.bind(stmt)
        self.pop_scope()

    def bind_GlobalFuncDef(self, decl: ast.GlobalFuncDef) -> None:
        self.bind_FuncDef(decl.funcdef)

    def bind_If(self, ifstmt: ast.If) -> None:
        self.bind(ifstmt.test)
        then_scope = self.scopes[ifstmt, "then"]
        self.push_scope(then_scope)
        for stmt in ifstmt.then_body:
            self.bind(stmt)
        self.pop_scope()
        else_scope = self.scopes[ifstmt, "else"]
        self.push_scope(else_scope)
        for stmt in ifstmt.else_body:
            self.bind(stmt)
        self.pop_scope()

    def bind_For(self, forstmt: ast.For) -> None:
        self.bind(forstmt.iter)
        # the hidden `_$iter` lives in the enclosing scope, as it is initialized outside
        # the desugared `while`.
        self.lookup_and_bind(forstmt, "_$iter", forstmt.iter.loc)
        body_scope = self.scopes[forstmt, "body"]
        self.push_scope(body_scope)
        tgt = forstmt.target
        self.lookup_and_bind(tgt, tgt.value, tgt.loc)
        for stmt in forstmt.body:
            self.bind(stmt)
        self.pop_scope()

    def bind_VarDef(self, vardef: ast.VarDef) -> None:
        # a VarDef must have a local symbol in the current scope, get it
        sym = self.scope.lookup(vardef.name.value)
        assert sym.level == 0
        self.set_binding(vardef, self.scope, sym)
        self.bind(vardef.type)
        if vardef.value is not None:
            self.bind(vardef.value)

    def bind_Assign(self, assign: ast.Assign) -> None:
        self.bind(assign.value)
        if isinstance(assign.target, ast.SingleTarget):
            # record the target StrLiteral -> sym.  astcompile reuses this same
            # StrLiteral node when it synthesizes the AssignExpr.
            tgt = assign.target.name
            self.lookup_and_bind(tgt, tgt.value, tgt.loc)
        else:
            # UnpackTarget: not migrated yet
            assert False, "TODO"
            ## self.bind(assign.target)

    def bind_AssignExpr(self, assignexpr: ast.AssignExpr) -> None:
        # walrus `x := E`
        self.bind(assignexpr.value)
        tgt = assignexpr.target
        self.lookup_and_bind(tgt, tgt.value, tgt.loc)

    def bind_Name(self, name: ast.Name) -> None:
        self.lookup_and_bind(name, name.id, name.loc)
