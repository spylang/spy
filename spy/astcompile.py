"""
astcompile pass

The main job of this pass is to resolve names and symbols using the symtable collected
by ScopeAnalyzer.  In particular rewrites generic ast.Name into more specific
ast.NameLocalDirect, ast.NameOuterDirect, etc.

Moreover, do other easy desugaring like converting `for` loops into `while` loops, etc.
"""

from typing import TYPE_CHECKING, Optional

import spy.ast as ast
from spy.analyze.symtable import Scope, Symbol, SymTable
from spy.ast import LoweringStage
from spy.errors import WIP, SPyError
from spy.location import Loc
from spy.util import magic_dispatch

if TYPE_CHECKING:
    from spy.analyze.scope2 import ScopeAnalyzer as ScopeAnalyzer2


def astcompile(
    parsed_mod: ast.Module,
    scope_analyzer: Optional["ScopeAnalyzer2"] = None,
) -> ast.Module:
    assert parsed_mod.stage == "parsed"
    compiled_mod = ASTCompiler(parsed_mod, scope_analyzer=scope_analyzer).compile_mod()
    assert compiled_mod.stage == "astcompiled"
    compiled_mod.assert_valid_at("astcompiled")
    return compiled_mod


def astcompile_interactive(expr: ast.Expr, scope: Scope) -> ast.Expr:
    """
    Compile a single expression in interactive mode.  The names are looked up in the
    given scope and its parents.  This is meant to be used by SPdb.
    """
    compiler = ASTCompiler(None, interactive_scope=scope)
    compiler.push_symtable(scope.symtable)
    return compiler.compile_expr(expr)


class ASTCompiler:
    def __init__(
        self,
        mod: Optional[ast.Module],
        *,
        scope_analyzer: Optional["ScopeAnalyzer2"] = None,
        interactive_scope: Optional[Scope] = None,
    ) -> None:
        # we support two compilation modes:
        #   - AOT, the default: we pass mod and scope_analyzer, names are resolved using
        #     scope_analyzer
        #   - interactive, for spdb: we pass interactive_scope and we use it for
        #     resolving names
        self.mod = mod
        self.symtable_stack: list[SymTable] = []
        self.sa = scope_analyzer
        self.interactive_scope = interactive_scope

    def push_symtable(self, symtable: SymTable) -> None:
        self.symtable_stack.append(symtable)

    def pop_symtable(self) -> SymTable:
        return self.symtable_stack.pop()

    @property
    def symtable(self) -> SymTable:
        return self.symtable_stack[-1]

    def compile_mod(self) -> ast.Module:
        assert self.mod is not None
        assert self.sa is not None
        mod_symtable = self.sa.by_module()
        self.push_symtable(mod_symtable)
        new_decls = [self.compile_decl(decl) for decl in self.mod.decls]
        self.pop_symtable()
        return self.mod.replace(
            stage="astcompiled",
            decls=new_decls,
            _symtable=mod_symtable,
        )

    def compile_decl(self, decl: ast.Decl) -> ast.Decl:
        return magic_dispatch(self, "compile_decl", decl)

    def compile_stmt(self, stmt: ast.Stmt) -> list[ast.Stmt]:
        # if we are in a ClassDef, only a few stmts are actually allowed
        in_classdef = self.symtable.kind == "class"
        allowed = (
            ast.VarDef,
            ast.Assign,
            ast.If,
            ast.Pass,
            ast.FuncDef,
        )
        if in_classdef and type(stmt) not in allowed:
            STMT = type(stmt).__name__
            raise SPyError.simple(
                "W_SyntaxError",
                f"`{STMT}` not supported inside a classdef",
                "this is not supported",
                stmt.loc,
            )
        return magic_dispatch(self, "compile_stmt", stmt)

    def compile_stmts(self, body: list[ast.Stmt]) -> list[ast.Stmt]:
        result = []
        for stmt in body:
            result.extend(self.compile_stmt(stmt))
        return result

    def compile_block(self, block: ast.Block) -> ast.Block:
        return block.replace(body=self.compile_stmts(block.body))

    def compile_expr(self, expr: ast.Expr) -> ast.Expr:
        return magic_dispatch(self, "compile_expr", expr)

    # ===== Decl handlers =====

    def compile_decl_GlobalFuncDef(self, decl: ast.GlobalFuncDef) -> ast.Decl:
        new_funcdef = self.compile_funcdef(decl.funcdef)
        return decl.replace(funcdef=new_funcdef)

    def compile_decl_GlobalGenericFuncDef(
        self, decl: ast.GlobalGenericFuncDef
    ) -> ast.Decl:
        gfuncdef = decl.funcdef
        # desugar into a `FuncDef(kind="generic")` here, so the GenericFuncDef node
        # never reaches the runtime (like for/augassign).
        outer_funcdef = self._desugar_generic(
            gfuncdef, gfuncdef.name, gfuncdef.args, gfuncdef.inner
        )
        return ast.GlobalFuncDef(decl.loc, outer_funcdef)

    def compile_decl_GlobalGenericClassDef(
        self, decl: ast.GlobalGenericClassDef
    ) -> ast.Decl:
        gclassdef = decl.classdef
        # desugar into a `FuncDef(kind="generic")` here.
        outer_funcdef = self._desugar_generic(
            gclassdef, gclassdef.name, gclassdef.args, gclassdef.inner
        )
        return ast.GlobalFuncDef(decl.loc, outer_funcdef)

    def _desugar_generic(
        self,
        node: ast.Node,
        name: str,
        args: list[ast.FuncArg],
        inner: ast.Stmt,
    ) -> ast.FuncDef:
        # desugar:
        #   def add[T](x: T, y: T) -> T:
        #       ...
        #
        # into:
        #   @blue
        #   def add(T):
        #       def __impl(x: T, y: T) -> T:
        #           ...
        #       return __impl
        #
        # (same for class[T])

        assert self.sa is not None
        assert self.mod is not None
        loc = inner.loc
        # the generic args and body are compiled in the outer generic frame
        outer_symtable = self.sa.get_symtable(node)
        self.push_symtable(outer_symtable)
        new_args = [
            arg.replace(
                type=self.compile_expr(arg.type),
                _sym=self.sa.get_resolved_sym(arg),
            )
            for arg in args
        ]

        # compile the inner def/class as the first body statement...
        new_inner = self.compile_stmt(inner)
        assert len(new_inner) == 1
        # synthesize `return <inner>`
        inner_sym = self.sa.get_resolved_sym(inner)
        return_stmt = ast.Return(
            loc=loc,
            value=ast.NameLocalDirect(loc=loc, sym=inner_sym),
        )
        self.pop_symtable()

        body = ast.Block(
            loc=loc, body=new_inner + [return_stmt], scope=self.sa.scopes[node]
        )
        return ast.FuncDef(
            loc=loc,
            stage="astcompiled",
            color="blue",
            kind="generic",
            name=name,
            args=new_args,
            return_type=ast.Auto(loc),
            defaults=[],
            docstring=None,
            scoping_rules=self.mod.scoping_rules,
            body=body,
            decorators=[],
            _symtable=outer_symtable,
            _sym=self.sa.get_resolved_sym(node),
        )

    def compile_decl_GlobalVarDef(self, decl: ast.GlobalVarDef) -> ast.Decl:
        new_vardef = self.compile_stmt_VarDef(decl.vardef)
        assert isinstance(new_vardef, list) and len(new_vardef) == 1
        assert isinstance(new_vardef[0], ast.VarDef)
        return decl.replace(vardef=new_vardef[0])

    def compile_decl_GlobalClassDef(self, decl: ast.GlobalClassDef) -> ast.Decl:
        new_classdef = self.compile_classdef(decl.classdef)
        return decl.replace(classdef=new_classdef)

    def compile_decl_Import(self, decl: ast.Import) -> ast.Decl:
        return decl

    # ===== FuncDef =====

    def compile_funcdef(self, funcdef: ast.FuncDef) -> ast.FuncDef:
        assert self.sa is not None
        # decorators, arg types, return type and defaults are evaluated in the outer scope
        new_decorators = [self.compile_expr(d) for d in funcdef.decorators]
        new_return_type = self.compile_expr(funcdef.return_type)
        new_args = [
            arg.replace(
                type=self.compile_expr(arg.type),
                _sym=self.sa.get_resolved_sym(arg),
            )
            for arg in funcdef.args
        ]
        new_defaults = [self.compile_expr(d) for d in funcdef.defaults]

        # the statements of the function are evaluated in the inner scope
        inner_symtable = self.sa.get_symtable(funcdef)
        self.push_symtable(inner_symtable)
        new_body = self.compile_block(funcdef.body)
        self.pop_symtable()
        new_sym = self.sa.get_resolved_sym(funcdef)
        return funcdef.replace(
            stage="astcompiled",
            decorators=new_decorators,
            return_type=new_return_type,
            args=new_args,
            defaults=new_defaults,
            body=new_body,
            _symtable=inner_symtable,
            _sym=new_sym,
        )

    # ===== Stmt handlers =====
    # Each handler returns list[ast.Stmt]. Usually it's a list of one,
    # but For desugaring returns two stmts.

    def compile_stmt_Return(self, ret: ast.Return) -> list[ast.Stmt]:
        return [ret.replace(value=self.compile_expr(ret.value))]

    def compile_stmt_Raise(self, stmt: ast.Raise) -> list[ast.Stmt]:
        return [stmt.replace(exc=self.compile_expr(stmt.exc))]

    def compile_stmt_Pass(self, stmt: ast.Pass) -> list[ast.Stmt]:
        return [stmt]

    def compile_stmt_Break(self, stmt: ast.Break) -> list[ast.Stmt]:
        return [stmt]

    def compile_stmt_Continue(self, stmt: ast.Continue) -> list[ast.Stmt]:
        return [stmt]

    def compile_stmt_Global(self, stmt: ast.Global) -> list[ast.Stmt]:
        # `global x` has effect only at ScopeAnalyzer time, no runtime effect.
        return []

    def compile_stmt_Nonlocal(self, stmt: ast.Nonlocal) -> list[ast.Stmt]:
        raise WIP("`nonlocal` is not implemented yet")

    def compile_stmt_VarDef(self, stmt: ast.VarDef) -> list[ast.Stmt]:
        assert self.sa is not None
        new_type = self.compile_expr(stmt.type)
        new_value = self.compile_expr(stmt.value) if stmt.value is not None else None
        # scope2 resolves every VarDef to a Symbol; fill it in so that the
        # runtime indexes the frame by sym.slot_name.
        sym = self.sa.get_resolved_sym_maybe(stmt)
        assert sym is not None
        return [stmt.replace(type=new_type, value=new_value, _sym=sym)]

    def compile_stmt_Assign(self, stmt: ast.Assign) -> list[ast.Stmt]:
        if isinstance(stmt.target, ast.SingleTarget):
            # this is a simple `x = E`:
            #   - synthesize the equivalent `x := E` AssignExpr
            #   - compile the AssignExpr
            #   - wrap the result into the appropriate Stmt
            expr: ast.Expr
            assign: ast.Stmt
            expr = ast.AssignExpr(stmt.loc, stmt.target.name, stmt.value)
            expr = self.compile_expr(expr)
            if isinstance(expr, ast.AssignExprLocal):
                assign = ast.AssignLocal(stmt.loc, expr)
            elif isinstance(expr, ast.AssignExprCell):
                assign = ast.AssignCell(stmt.loc, expr)
            elif isinstance(expr, ast.PoisonExpr):
                # assignment to a const: the poison sits in statement position
                assign = ast.StmtExpr(stmt.loc, expr)
            else:
                assert False, "unknown AssignExpr node"
            return [assign]

        elif isinstance(stmt.target, ast.UnpackTarget):
            # TODO: support nested unpack targets (e.g. (a, (b, c)) = ...)
            targets = []
            for t in stmt.target.targets:
                if not isinstance(t, ast.SingleTarget):
                    raise WIP("nested unpack targets are not supported yet")
                name = t.name
                assert self.sa is not None
                sym = self.sa.get_resolved_sym(name)
                name = ast.StrLiteral(name.loc, sym.slot_name)
                targets.append(name)
            return [
                ast.AssignUnpack(
                    loc=stmt.loc,
                    targets=targets,
                    value=self.compile_expr(stmt.value),
                )
            ]

        else:
            assert False

    def compile_stmt_AssignTemp(self, stmt: ast.AssignTemp) -> list[ast.Stmt]:
        # a write to a hidden compiler temp; lower directly to AssignLocal, no lookup.
        value = self.compile_expr(stmt.value)
        target = ast.StrLiteral(stmt.loc, stmt.sym.slot_name)
        assign_expr = ast.AssignExprLocal(stmt.loc, target, stmt.sym, value)
        return [ast.AssignLocal(stmt.loc, assign_expr)]

    def compile_stmt_ClassDef(self, stmt: ast.ClassDef) -> list[ast.Stmt]:
        return [self.compile_classdef(stmt)]

    def compile_classdef(self, classdef: ast.ClassDef) -> ast.ClassDef:
        assert self.sa is not None
        inner_symtable = self.sa.get_symtable(classdef)
        new_sym = self.sa.get_resolved_sym(classdef)
        self.push_symtable(inner_symtable)
        new_body = self.compile_block(classdef.body)
        self.pop_symtable()
        return classdef.replace(body=new_body, _symtable=inner_symtable, _sym=new_sym)

    def compile_stmt_FuncDef(self, stmt: ast.FuncDef) -> list[ast.Stmt]:
        return [self.compile_funcdef(stmt)]

    def compile_stmt_For(self, stmt: ast.For) -> list[ast.Stmt]:
        # desugar:
        #   for i in X:
        #       body
        # into:
        #   $_iter = X.__fastiter__()
        #   while $_iter.__continue_iteration__():
        #       i = $_iter.__item__()
        #       $_iter = $_iter.__next__()
        #       body
        loc = stmt.loc
        # use non-colorize locs for synthetic nodes, to avoid painting over user nodes
        iter_loc = stmt.iter.loc.replace(colorize=False)
        target_loc = stmt.target.loc.replace(colorize=False)
        iter_sym = self.symtable.make_temp_symbol("_$iter", iter_loc)  # e.g. _$iter$0

        init_iter = ast.AssignTemp(
            loc=iter_loc,
            sym=iter_sym,
            value=ast.CallMethod(
                loc=iter_loc,
                target=stmt.iter,
                method=ast.StrLiteral(iter_loc, "__fastiter__"),
                args=[],
            ),
        )
        assign_item = ast.Assign(
            loc=target_loc,
            target=ast.SingleTarget(target_loc, stmt.target),
            value=ast.CallMethod(
                loc=target_loc,
                target=ast.NameTemp(iter_loc, iter_sym),
                method=ast.StrLiteral(target_loc, "__item__"),
                args=[],
            ),
        )
        advance_iter = ast.AssignTemp(
            loc=iter_loc,
            sym=iter_sym,
            value=ast.CallMethod(
                loc=iter_loc,
                target=ast.NameTemp(iter_loc, iter_sym),
                method=ast.StrLiteral(iter_loc, "__next__"),
                args=[],
            ),
        )
        # NOTE: the synthesized `while` gets its .scope from for.body.scope
        while_loop = ast.While(
            loc=loc,
            test=ast.CallMethod(
                loc=iter_loc,
                target=ast.NameTemp(iter_loc, iter_sym),
                method=ast.StrLiteral(iter_loc, "__continue_iteration__"),
                args=[],
            ),
            body=stmt.body.replace(
                body=[assign_item, advance_iter] + stmt.body.body,
            ),
        )
        compiled_init = self.compile_stmt(init_iter)
        compiled_while = self.compile_stmt(while_loop)
        return compiled_init + compiled_while

    def compile_stmt_AugAssign(self, stmt: ast.AugAssign) -> list[ast.Stmt]:
        # desugar "x += 1" into "x = x + 1" and compile the result.
        # use non-colorize locs for synthetic nodes, to avoid painting over user nodes
        binop_loc = stmt.loc.replace(colorize=False)
        target_loc = stmt.target.loc.replace(colorize=False)
        read_name = ast.Name(loc=target_loc, id=stmt.target.value)
        assert self.sa is not None
        # we must bind the synthetic node
        scope = self.sa.get_resolved_scope(stmt.target)
        res = self.sa.get_resolution(stmt.target)
        self.sa.bind_synthetic_node(read_name, scope, res)
        desugared = ast.Assign(
            loc=stmt.loc,
            target=ast.SingleTarget(target_loc, stmt.target),
            value=ast.BinOp(
                loc=binop_loc,
                op=stmt.op,
                left=read_name,
                right=stmt.value,
            ),
        )
        return self.compile_stmt(desugared)

    def compile_stmt_AugSetAttr(self, stmt: ast.AugSetAttr) -> list[ast.Stmt]:
        # we have:
        #   obj.attr OP= v
        #
        # we want to evaluate `obj` only once. We desugar into:
        #   _$t = obj
        #   _$t.attr = _$t.attr OP v
        target_loc = stmt.target.loc.replace(colorize=False)
        value_loc = stmt.loc.replace(colorize=False)
        target_sym = self.symtable.make_temp_symbol("_$t", target_loc)

        desugared: list[ast.Stmt] = [
            ast.AssignTemp(loc=target_loc, sym=target_sym, value=stmt.target),
            ast.SetAttr(
                loc=stmt.loc,
                target=ast.NameTemp(target_loc, target_sym),
                attr=stmt.attr,
                value=ast.BinOp(
                    loc=value_loc,
                    op=stmt.op,
                    left=ast.GetAttr(
                        loc=target_loc,
                        value=ast.NameTemp(target_loc, target_sym),
                        attr=stmt.attr,
                    ),
                    right=stmt.value,
                ),
            ),
        ]
        return self.compile_stmts(desugared)

    def compile_stmt_AugSetItem(self, stmt: ast.AugSetItem) -> list[ast.Stmt]:
        # we have:
        #   obj[arg0, arg1, ...] OP= v
        #
        # we want to evaluate `obj` and each `arg` only once. We desugar into:
        #   _$t = obj
        #   _$a0 = arg0
        #   _$a1 = arg1
        #   _$t[_$a0, _$a1, ...] = _$t[_$a0, _$a1, ...] OP v
        target_loc = stmt.target.loc.replace(colorize=False)
        value_loc = stmt.loc.replace(colorize=False)
        target_sym = self.symtable.make_temp_symbol("_$t", target_loc)

        desugared: list[ast.Stmt] = [
            ast.AssignTemp(loc=target_loc, sym=target_sym, value=stmt.target)
        ]
        arg_syms = []
        for arg in stmt.args:
            arg_loc = arg.loc.replace(colorize=False)
            arg_sym = self.symtable.make_temp_symbol("_$a", arg_loc)
            arg_syms.append((arg_sym, arg_loc))
            desugared.append(ast.AssignTemp(loc=arg_loc, sym=arg_sym, value=arg))

        lhs_args: list[ast.Expr] = [ast.NameTemp(loc, sym) for sym, loc in arg_syms]
        rhs_args: list[ast.Expr] = [ast.NameTemp(loc, sym) for sym, loc in arg_syms]

        desugared.append(
            ast.SetItem(
                loc=stmt.loc,
                target=ast.NameTemp(target_loc, target_sym),
                args=lhs_args,
                value=ast.BinOp(
                    loc=value_loc,
                    op=stmt.op,
                    left=ast.GetItem(
                        loc=target_loc,
                        value=ast.NameTemp(target_loc, target_sym),
                        args=rhs_args,
                    ),
                    right=stmt.value,
                ),
            )
        )
        return self.compile_stmts(desugared)

    def compile_stmt_SetItem(self, stmt: ast.SetItem) -> list[ast.Stmt]:
        return [
            stmt.replace(
                target=self.compile_expr(stmt.target),
                args=[self.compile_expr(a) for a in stmt.args],
                value=self.compile_expr(stmt.value),
            )
        ]

    def compile_stmt_SetAttr(self, stmt: ast.SetAttr) -> list[ast.Stmt]:
        return [
            stmt.replace(
                target=self.compile_expr(stmt.target),
                value=self.compile_expr(stmt.value),
            )
        ]

    def compile_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> list[ast.Stmt]:
        return [stmt.replace(value=self.compile_expr(stmt.value))]

    def compile_stmt_While(self, stmt: ast.While) -> list[ast.Stmt]:
        return [
            stmt.replace(
                test=self.compile_expr(stmt.test),
                body=self.compile_block(stmt.body),
            )
        ]

    def compile_stmt_Assert(self, stmt: ast.Assert) -> list[ast.Stmt]:
        new_msg = self.compile_expr(stmt.msg) if stmt.msg is not None else None
        return [
            stmt.replace(
                test=self.compile_expr(stmt.test),
                msg=new_msg,
            )
        ]

    def compile_stmt_If(self, stmt: ast.If) -> list[ast.Stmt]:
        return [
            stmt.replace(
                test=self.compile_expr(stmt.test),
                then=self.compile_block(stmt.then),
                else_=self.compile_block(stmt.else_),
            )
        ]

    # ===== Expr handlers =====

    def compile_expr_Auto(self, auto: ast.Auto) -> ast.Expr:
        return auto

    def compile_expr_FQNConst(self, expr: ast.FQNConst) -> ast.Expr:
        return expr

    def compile_expr_StrLiteral(self, lit: ast.StrLiteral) -> ast.Expr:
        return lit

    def compile_expr_BytesLiteral(self, lit: ast.BytesLiteral) -> ast.Expr:
        return lit

    def compile_expr_BinOp(self, expr: ast.BinOp) -> ast.Expr:
        return expr.replace(
            left=self.compile_expr(expr.left),
            right=self.compile_expr(expr.right),
        )

    def compile_expr_CmpOp(self, expr: ast.CmpOp) -> ast.Expr:
        return expr.replace(
            left=self.compile_expr(expr.left),
            right=self.compile_expr(expr.right),
        )

    def compile_expr_Literal(self, expr: ast.Literal) -> ast.Expr:
        return expr

    def compile_expr_Slice(self, expr: ast.Slice) -> ast.Expr:
        return expr.replace(
            start=self.compile_expr(expr.start),
            stop=self.compile_expr(expr.stop),
            step=self.compile_expr(expr.step),
        )

    def compile_expr_GetItem(self, expr: ast.GetItem) -> ast.Expr:
        return expr.replace(
            value=self.compile_expr(expr.value),
            args=[self.compile_expr(a) for a in expr.args],
        )

    def compile_expr_GetAttr(self, expr: ast.GetAttr) -> ast.Expr:
        return expr.replace(value=self.compile_expr(expr.value))

    def compile_expr_UnaryOp(self, expr: ast.UnaryOp) -> ast.Expr:
        return expr.replace(value=self.compile_expr(expr.value))

    def compile_expr_And(self, expr: ast.And) -> ast.Expr:
        return expr.replace(
            left=self.compile_expr(expr.left),
            right=self.compile_expr(expr.right),
        )

    def compile_expr_Or(self, expr: ast.Or) -> ast.Expr:
        return expr.replace(
            left=self.compile_expr(expr.left),
            right=self.compile_expr(expr.right),
        )

    def compile_expr_CallMethod(self, expr: ast.CallMethod) -> ast.Expr:
        return expr.replace(
            target=self.compile_expr(expr.target),
            args=[self.compile_expr(a) for a in expr.args],
        )

    def compile_expr_Call(self, expr: ast.Call) -> ast.Expr:
        return expr.replace(
            func=self.compile_expr(expr.func),
            args=[self.compile_expr(arg) for arg in expr.args],
        )

    def compile_expr_List(self, expr: ast.List) -> ast.Expr:
        return expr.replace(items=[self.compile_expr(item) for item in expr.items])

    def compile_expr_Tuple(self, expr: ast.Tuple) -> ast.Expr:
        return expr.replace(items=[self.compile_expr(item) for item in expr.items])

    def compile_expr_Dict(self, expr: ast.Dict) -> ast.Expr:
        new_items = [
            item.replace(
                key=self.compile_expr(item.key), value=self.compile_expr(item.value)
            )
            for item in expr.items
        ]
        return expr.replace(items=new_items)

    def compile_expr_BlockExpr(self, expr: ast.BlockExpr) -> ast.Expr:
        return expr.replace(
            body=self.compile_stmts(expr.body),
            value=self.compile_expr(expr.value),
        )

    def compile_expr_AssignExpr(self, expr: ast.AssignExpr) -> ast.Expr:
        target = expr.target
        assert self.sa is not None
        if (err := self.sa.get_poison_error_maybe(target)) is not None:
            return ast.PoisonExpr(expr.loc, err)
        sym = self.sa.get_resolved_sym(target)

        value = self.compile_expr(expr.value)

        if sym.varkind == "const" and sym.varkind_origin != "auto":
            # assignment to a const: resolve to a lazy poison error
            err = SPyError("W_TypeError", "invalid assignment target")
            err.add("error", f"{sym.src_name} is const", target.loc)
            err.add("note", f"const declared here ({sym.varkind_origin})", sym.loc)
            if sym.varkind_origin == "global-const":
                msg = f"help: declare it as variable: `var {sym.src_name} ...`"
                err.add("note", msg, sym.loc)
            elif sym.varkind_origin == "blue-param":
                msg = "blue function arguments are const by default"
                err.add("note", msg, sym.loc)
            return ast.PoisonExpr(expr.loc, err)

        if sym.storage == "direct":
            assert sym.is_local
            return ast.AssignExprLocal(expr.loc, target, sym, value)

        elif sym.storage == "cell":
            assert not sym.is_local
            return ast.AssignExprCell(
                loc=expr.loc,
                target=target,
                target_fqn=None,
                sym=sym,
                value=value,
            )

        else:
            assert False, f"unexpected storage: {sym.storage!r}"

    def compile_expr_NameTemp(self, name: ast.NameTemp) -> ast.Expr:
        # a hidden compiler temp carries its own Symbol; lower directly, no lookup.
        return ast.NameLocalDirect(name.loc, name.sym)

    def compile_expr_Name(self, name: ast.Name) -> ast.Expr:
        if self.interactive_scope is not None:
            return self._resolve_interactive(name)
        assert self.sa is not None
        # scope2: a name resolves either to a Symbol or to a lazy SPyError
        err = self.sa.get_poison_error_maybe(name)
        if err is not None:
            return ast.PoisonExpr(name.loc, err)
        sym = self.sa.get_resolved_sym_maybe(name)
        assert sym is not None, "sym not found"
        return self._emit_name_node(name.loc, sym)

    def _emit_name_node(self, loc: Loc, sym: Symbol) -> ast.Expr:
        if sym.impref is not None:
            return ast.NameImportRef(loc, sym)
        elif sym.storage == "direct" and sym.is_local:
            return ast.NameLocalDirect(loc, sym)
        elif sym.storage == "direct":
            return ast.NameOuterDirect(loc, sym)
        elif sym.storage == "cell" and sym.is_local:
            return ast.NameLocalCell(loc, sym)
        elif sym.storage == "cell" and not sym.is_local:
            return ast.NameOuterCell(loc, sym, fqn=None)
        else:
            assert False, f"unexpected storage: {sym.storage!r}"

    def _resolve_interactive(self, name: ast.Name) -> ast.Expr:
        """
        Resolve a name against self.interactive_scope. This is used by interactive
        compilation for e.g. spdb.
        """
        assert self.interactive_scope is not None
        res = self.interactive_scope.lookup(name.id)
        if res.found:
            assert res.sym is not None
            # this is the equivalent of what we do in ScopeAnalyzer.lookup_and_bind
            new_sym = res.sym.replace(level=res.level)
            return self._emit_name_node(name.loc, new_sym)

        # not found
        err = SPyError("W_NameError", f"name `{name.id}` is not defined")
        err.add("error", "not found in this scope", name.loc)
        return ast.PoisonExpr(name.loc, err)
