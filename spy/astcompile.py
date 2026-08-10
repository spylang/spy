"""
astcompile pass

The main job of this pass is to resolve names and symbols using the symtable collected
by ScopeAnalyzer.  In particular rewrites generic ast.Name into more specific
ast.NameLocalDirect, ast.NameOuterDirect, etc.

Moreover, do other easy desugaring like converting `for` loops into `while` loops, etc.
"""

import spy.ast as ast
from spy.analyze.symtable import SymTable
from spy.ast import LoweringStage
from spy.errors import WIP
from spy.util import magic_dispatch


def astcompile(parsed_mod: ast.Module) -> ast.Module:
    assert parsed_mod.stage == "parsed"
    compiled_mod = ASTCompiler(parsed_mod).compile_mod()
    assert compiled_mod.stage == "astcompiled"
    compiled_mod.assert_valid_at("astcompiled")
    return compiled_mod


class ASTCompiler:
    def __init__(self, mod: ast.Module) -> None:
        self.mod = mod
        self.symtable_stack: list[SymTable] = []

    def push_symtable(self, symtable: SymTable) -> None:
        self.symtable_stack.append(symtable)

    def pop_symtable(self) -> SymTable:
        return self.symtable_stack.pop()

    @property
    def symtable(self) -> SymTable:
        return self.symtable_stack[-1]

    def compile_mod(self) -> ast.Module:
        self.push_symtable(self.mod.symtable)
        new_decls = [self.compile_decl(decl) for decl in self.mod.decls]
        self.pop_symtable()
        return self.mod.replace(
            stage="astcompiled",
            decls=new_decls,
        )

    def compile_decl(self, decl: ast.Decl) -> ast.Decl:
        return magic_dispatch(self, "compile_decl", decl)

    def compile_stmt(self, stmt: ast.Stmt) -> list[ast.Stmt]:
        return magic_dispatch(self, "compile_stmt", stmt)

    def compile_stmts(self, stmts: list[ast.Stmt]) -> list[ast.Stmt]:
        result = []
        for stmt in stmts:
            result.extend(self.compile_stmt(stmt))
        return result

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
        self.push_symtable(gfuncdef.symtable)
        new_inner = self.compile_funcdef(gfuncdef.inner)
        self.pop_symtable()
        new_gfuncdef = gfuncdef.replace(inner=new_inner)
        return decl.replace(funcdef=new_gfuncdef)

    def compile_decl_GlobalGenericClassDef(
        self, decl: ast.GlobalGenericClassDef
    ) -> ast.Decl:
        # GenericClassDef is basically _function_ which returns a class. So when
        # evaluating the body we need to push:
        #     gclassdef.symtable which contains e.g. 'T'
        #     inner.symtable which contains the body of the class
        gclassdef = decl.classdef
        inner = gclassdef.inner
        self.push_symtable(gclassdef.symtable)
        self.push_symtable(inner.symtable)
        new_body = self.compile_stmts(inner.body)
        self.pop_symtable()
        self.pop_symtable()
        new_inner = inner.replace(body=new_body)
        new_gclassdef = gclassdef.replace(inner=new_inner)
        return decl.replace(classdef=new_gclassdef)

    def compile_decl_GlobalVarDef(self, decl: ast.GlobalVarDef) -> ast.Decl:
        new_vardef = self.compile_stmt_VarDef(decl.vardef)
        assert isinstance(new_vardef, list) and len(new_vardef) == 1
        assert isinstance(new_vardef[0], ast.VarDef)
        return decl.replace(vardef=new_vardef[0])

    def compile_decl_GlobalClassDef(self, decl: ast.GlobalClassDef) -> ast.Decl:
        classdef = decl.classdef
        self.push_symtable(classdef.symtable)
        new_body = self.compile_stmts(classdef.body)
        self.pop_symtable()
        new_classdef = classdef.replace(body=new_body)
        return decl.replace(classdef=new_classdef)

    def compile_decl_Import(self, decl: ast.Import) -> ast.Decl:
        return decl

    # ===== FuncDef =====

    def compile_funcdef(self, funcdef: ast.FuncDef) -> ast.FuncDef:
        # decorators, arg types, return type and defaults are evaluated in the outer scope
        new_decorators = [self.compile_expr(d) for d in funcdef.decorators]
        new_return_type = self.compile_expr(funcdef.return_type)
        new_args = [
            arg.replace(type=self.compile_expr(arg.type)) for arg in funcdef.args
        ]
        ## for default in funcdef.defaults:
        ##     pass

        # the statements of the function are evaluated in the inner scope
        self.push_symtable(funcdef.symtable)
        new_body = self.compile_stmts(funcdef.body)
        self.pop_symtable()
        return funcdef.replace(
            stage="astcompiled",
            decorators=new_decorators,
            return_type=new_return_type,
            args=new_args,
            body=new_body,
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

    def compile_stmt_VarDef(self, stmt: ast.VarDef) -> list[ast.Stmt]:
        new_type = self.compile_expr(stmt.type)
        new_value = self.compile_expr(stmt.value) if stmt.value is not None else None
        return [stmt.replace(type=new_type, value=new_value)]

    def _compile_assign_common(
        self, loc: ast.Loc, target: ast.StrLiteral, value: ast.Expr, expr: bool
    ) -> (
        ast.AssignLocal
        | ast.AssignExprLocal
        | ast.AssignConstError
        | ast.AssignConstExprError
    ):
        value = self.compile_expr(value)
        sym = self.symtable.lookup(target.value)

        if sym.varkind == "const" and sym.varkind_origin != "auto":
            # this is an error, let's insert the appropriate poison node
            if expr:
                return ast.AssignConstExprError(loc, sym, target.loc)
            else:
                return ast.AssignConstError(loc, sym, target.loc)

        if sym.storage == "direct":
            assert sym.is_local
            if expr:
                return ast.AssignExprLocal(loc, target, value)
            else:
                return ast.AssignLocal(loc, target, value)

        elif sym.storage == "cell":
            assert not sym.is_local
            if expr:
                return ast.AssignExprCell(
                    loc=loc,
                    target=target,
                    target_fqn=None,
                    sym=sym,
                    value=value,
                )
            else:
                return ast.AssignCell(
                    loc=loc,
                    target=target,
                    target_fqn=None,
                    sym=sym,
                    value=value,
                )

        else:
            assert False, f"unexpected storage: {sym.storage!r}"

    def compile_stmt_Assign(self, stmt: ast.Assign) -> list[ast.Stmt]:
        if isinstance(stmt.target, ast.SingleTarget):
            return [
                self._compile_assign_common(
                    stmt.loc, stmt.target.name, stmt.value, expr=False
                )
            ]

        elif isinstance(stmt.target, ast.UnpackTarget):
            # TODO: support nested unpack targets (e.g. (a, (b, c)) = ...)
            targets = []
            for t in stmt.target.targets:
                if isinstance(t, ast.SingleTarget):
                    targets.append(t.name)
                else:
                    raise WIP("nested unpack targets are not supported yet")
            return [
                ast.AssignUnpack(
                    loc=stmt.loc,
                    targets=targets,
                    value=self.compile_expr(stmt.value),
                )
            ]

        else:
            assert False

    def compile_stmt_ClassDef(self, stmt: ast.ClassDef) -> list[ast.Stmt]:
        self.push_symtable(stmt.symtable)
        new_body = self.compile_stmts(stmt.body)
        self.pop_symtable()
        return [stmt.replace(body=new_body)]

    def compile_stmt_FuncDef(self, stmt: ast.FuncDef) -> list[ast.Stmt]:
        return [self.compile_funcdef(stmt)]

    def compile_stmt_For(self, stmt: ast.For) -> list[ast.Stmt]:
        # desugar:
        #   for i in X:
        #       body
        # into:
        #   it = X.__fastiter__()
        #   while it.__continue_iteration__():
        #       i = it.__item__()
        #       it = it.__next__()
        #       body
        loc = stmt.loc
        iter_name = f"_$iter{stmt.seq}"
        iter_target = ast.SingleTarget(loc, ast.StrLiteral(loc, iter_name))
        iter_name_node = ast.Name(loc=loc, id=iter_name)

        init_iter = ast.Assign(
            loc=loc,
            target=iter_target,
            value=ast.CallMethod(
                loc=loc,
                target=stmt.iter,
                method=ast.StrLiteral(loc, "__fastiter__"),
                args=[],
            ),
        )
        assign_item = ast.Assign(
            loc=loc,
            target=ast.SingleTarget(loc, stmt.target),
            value=ast.CallMethod(
                loc=loc,
                target=iter_name_node,
                method=ast.StrLiteral(loc, "__item__"),
                args=[],
            ),
        )
        advance_iter = ast.Assign(
            loc=loc,
            target=iter_target,
            value=ast.CallMethod(
                loc=loc,
                target=iter_name_node,
                method=ast.StrLiteral(loc, "__next__"),
                args=[],
            ),
        )
        while_loop = ast.While(
            loc=loc,
            test=ast.CallMethod(
                loc=loc,
                target=iter_name_node,
                method=ast.StrLiteral(loc, "__continue_iteration__"),
                args=[],
            ),
            body=[assign_item, advance_iter] + stmt.body,
        )
        compiled_init = self.compile_stmt(init_iter)
        compiled_while = self.compile_stmt(while_loop)
        return compiled_init + compiled_while

    def compile_stmt_AugAssign(self, stmt: ast.AugAssign) -> list[ast.Stmt]:
        # desugar "x += 1" into "x = x + 1" and compile the result
        desugared = ast.Assign(
            loc=stmt.loc,
            target=ast.SingleTarget(stmt.loc, stmt.target),
            value=ast.BinOp(
                loc=stmt.loc,
                op=stmt.op,
                left=ast.Name(loc=stmt.target.loc, id=stmt.target.value),
                right=stmt.value,
            ),
        )
        return self.compile_stmt(desugared)

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
                body=self.compile_stmts(stmt.body),
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
                then_body=self.compile_stmts(stmt.then_body),
                else_body=self.compile_stmts(stmt.else_body),
            )
        ]

    # ===== Expr handlers =====

    def compile_expr_Auto(self, auto: ast.Auto) -> ast.Expr:
        return auto

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

    def compile_expr_AssignExpr(self, expr: ast.AssignExpr) -> ast.Expr:
        return self._compile_assign_common(expr.loc, expr.target, expr.value, expr=True)

    def compile_expr_Name(self, name: ast.Name) -> ast.Expr:
        varname = name.id
        sym = self.symtable.lookup_maybe(varname)
        assert sym is not None

        # XXX: what about SPdb?
        ## if not self.is_interactive:
        ##     assert sym is not None

        ## if sym is None:
        ##     # sym can be None ONLY in interactive frames (in which case we do a dynamic
        ##     # lookup), else it means that there is a bug in symtable.
        ##     assert self.is_interactive, "sym not found"
        ##     # create a fake symbol to be used below
        ##     sym = Symbol(
        ##         varname,
        ##         "var",
        ##         "auto",
        ##         "NameError",
        ##         loc=name.loc,
        ##         type_loc=name.loc,
        ##         level=-1,
        ##     )

        if sym.impref is not None:
            return ast.NameImportRef(name.loc, sym)
        elif sym.storage == "direct" and sym.is_local:
            return ast.NameLocalDirect(name.loc, sym)
        elif sym.storage == "direct":
            return ast.NameOuterDirect(name.loc, sym)
        elif sym.storage == "cell" and sym.is_local:
            return ast.NameLocalCell(name.loc, sym)
        elif sym.storage == "cell" and not sym.is_local:
            return ast.NameOuterCell(name.loc, sym, fqn=None)
        elif sym.storage == "NameError":
            return ast.NameError(name.loc, name.id)
        else:
            assert False, f"unexpected storage: {sym.storage!r}"
