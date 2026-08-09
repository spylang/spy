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

    def compile_stmt(self, stmt: ast.Stmt) -> ast.Stmt:
        return magic_dispatch(self, "compile_stmt", stmt)

    def compile_expr(self, expr: ast.Expr) -> ast.Expr:
        return magic_dispatch(self, "compile_expr", expr)

    # ===== Decl handlers =====

    def compile_decl_GlobalFuncDef(self, decl: ast.GlobalFuncDef) -> ast.Decl:
        new_funcdef = self.compile_funcdef(decl.funcdef)
        return decl.replace(funcdef=new_funcdef)

    ## def compile_decl_GlobalGenericFuncDef(
    ##     self, decl: ast.GlobalGenericFuncDef
    ## ) -> ast.Decl:
    ##     return decl

    def compile_decl_GlobalVarDef(self, decl: ast.GlobalVarDef) -> ast.Decl:
        new_vardef = self.compile_stmt_VarDef(decl.vardef)
        assert isinstance(new_vardef, ast.VarDef)
        return decl.replace(vardef=new_vardef)

    ## def compile_decl_GlobalClassDef(self, decl: ast.GlobalClassDef) -> ast.Decl:
    ##     return decl

    ## def compile_decl_GlobalGenericClassDef(
    ##     self, decl: ast.GlobalGenericClassDef
    ## ) -> ast.Decl:
    ##     return decl

    def compile_decl_Import(self, decl: ast.Import) -> ast.Decl:
        return decl

    # ===== FuncDef =====

    def compile_funcdef(self, funcdef: ast.FuncDef) -> ast.FuncDef:
        # TODO: decorators are evaluated in the outer scope
        ## for decorator in funcdef.decorators:
        ##     pass
        #
        # arg types, return type and defaults are evaluated in the outer scope
        new_return_type = self.compile_expr(funcdef.return_type)
        new_args = [
            arg.replace(type=self.compile_expr(arg.type)) for arg in funcdef.args
        ]
        ## for default in funcdef.defaults:
        ##     pass

        # the statements of the function are evaluated in the inner scope
        self.push_symtable(funcdef.symtable)
        new_body = [self.compile_stmt(stmt) for stmt in funcdef.body]
        self.pop_symtable()
        return funcdef.replace(
            stage="astcompiled",
            return_type=new_return_type,
            args=new_args,
            body=new_body,
        )

    # ===== Stmt handlers =====

    def compile_stmt_Return(self, ret: ast.Return) -> ast.Stmt:
        return ret.replace(value=self.compile_expr(ret.value))

    def compile_stmt_Pass(self, stmt: ast.Pass) -> ast.Stmt:
        return stmt

    def compile_stmt_VarDef(self, stmt: ast.VarDef) -> ast.Stmt:
        new_type = self.compile_expr(stmt.type)
        new_value = self.compile_expr(stmt.value) if stmt.value is not None else None
        return stmt.replace(type=new_type, value=new_value)

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

    def compile_stmt_Assign(self, stmt: ast.Assign) -> ast.Stmt:
        assert isinstance(stmt.target, ast.SingleTarget)
        return self._compile_assign_common(
            stmt.loc, stmt.target.name, stmt.value, expr=False
        )

    def compile_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> ast.Stmt:
        return stmt.replace(value=self.compile_expr(stmt.value))

    def compile_stmt_While(self, stmt: ast.While) -> ast.Stmt:
        return stmt.replace(
            test=self.compile_expr(stmt.test),
            body=[self.compile_stmt(s) for s in stmt.body],
        )

    def compile_stmt_Assert(self, stmt: ast.Assert) -> ast.Stmt:
        new_msg = self.compile_expr(stmt.msg) if stmt.msg is not None else None
        return stmt.replace(
            test=self.compile_expr(stmt.test),
            msg=new_msg,
        )

    def compile_stmt_If(self, stmt: ast.If) -> ast.Stmt:
        return stmt.replace(
            test=self.compile_expr(stmt.test),
            then_body=[self.compile_stmt(s) for s in stmt.then_body],
            else_body=[self.compile_stmt(s) for s in stmt.else_body],
        )

    # ===== Expr handlers =====

    def compile_expr_Auto(self, auto: ast.Auto) -> ast.Expr:
        return auto

    def compile_expr_StrLiteral(self, lit: ast.StrLiteral) -> ast.Expr:
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

    def compile_expr_Call(self, expr: ast.Call) -> ast.Expr:
        return expr.replace(
            func=self.compile_expr(expr.func),
            args=[self.compile_expr(arg) for arg in expr.args],
        )

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
