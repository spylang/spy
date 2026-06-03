"""
Helpers for @force_inline: validation and inlining mechanics.
"""

from typing import TYPE_CHECKING

from spy import ast
from spy.analyze.symtable import Symbol
from spy.doppler import make_const
from spy.errors import SPyError
from spy.util import magic_dispatch
from spy.vm.function import W_ASTFunc
from spy.vm.primitive import TYPES

if TYPE_CHECKING:
    from spy.vm.object import W_Type
    from spy.vm.vm import SPyVM


def validate_force_inline(w_func: W_ASTFunc) -> None:
    body = w_func.funcdef.body
    last_stmt = body[-1] if body else None
    returns_none = w_func.w_functype.w_restype is TYPES.w_NoneType
    if not returns_none and not isinstance(last_stmt, ast.Return):
        err = SPyError(
            "W_TypeError",
            "@force_inline requires a single tail return",
        )
        err.add("error", "missing `return` at the end of the body", w_func.def_loc)
        raise err

    for ret in w_func.funcdef.walk(ast.Return):
        if ret is not last_stmt:
            err = SPyError(
                "W_TypeError",
                "@force_inline requires a single tail return",
            )
            err.add(
                "error",
                "`return` must be the last statement of the body",
                ret.loc,
            )
            raise err


class AlphaRenamer:
    """
    Deep-copy a redshifted function body, renaming every callee-local Symbol
    by appending suffix (e.g. "$0") to its name.
    """

    def __init__(self, funcdef: ast.FuncDef, suffix: str) -> None:
        self.funcdef = funcdef
        self.suffix = suffix
        self.sym_map: dict[Symbol, Symbol] = {}
        for sym in funcdef.symtable._symbols.values():
            if sym.is_local:
                new_name = f"{sym.name}{self.suffix}"
                self.sym_map[sym] = sym.replace(name=new_name)

    def get_new_symbols(self) -> list[Symbol]:
        return list(self.sym_map.values())

    def rename_sym(self, old_sym: Symbol) -> Symbol:
        return self.sym_map[old_sym]

    def rename_body(self) -> list[ast.Stmt]:
        return self._rename_stmts(self.funcdef.body)

    def _rename_stmts(self, stmts: list[ast.Stmt]) -> list[ast.Stmt]:
        return [self.rename_stmt(s) for s in stmts]

    def rename_stmt(self, stmt: ast.Stmt) -> ast.Stmt:
        return magic_dispatch(self, "rename_stmt", stmt)

    def rename_expr(self, expr: ast.Expr) -> ast.Expr:
        return magic_dispatch(self, "rename_expr", expr)

    # ---- statements ----

    def rename_stmt_Return(self, stmt: ast.Return) -> ast.Stmt:
        return stmt.replace(value=self.rename_expr(stmt.value))

    def rename_stmt_VarDef(self, stmt: ast.VarDef) -> ast.Stmt:
        old_name = stmt.name.value
        new_name_node = stmt.name.replace(value=f"{old_name}{self.suffix}")
        new_value = self.rename_expr(stmt.value) if stmt.value is not None else None
        return stmt.replace(name=new_name_node, value=new_value)

    def rename_stmt_AssignLocal(self, stmt: ast.AssignLocal) -> ast.Stmt:
        new_target = stmt.target.replace(value=f"{stmt.target.value}{self.suffix}")
        return stmt.replace(target=new_target, value=self.rename_expr(stmt.value))

    def rename_stmt_AssignCell(self, stmt: ast.AssignCell) -> ast.Stmt:
        new_target = stmt.target.replace(value=f"{stmt.target.value}{self.suffix}")
        return stmt.replace(target=new_target, value=self.rename_expr(stmt.value))

    def rename_stmt_If(self, stmt: ast.If) -> ast.Stmt:
        return stmt.replace(
            test=self.rename_expr(stmt.test),
            then_body=self._rename_stmts(stmt.then_body),
            else_body=self._rename_stmts(stmt.else_body),
        )

    def rename_stmt_While(self, stmt: ast.While) -> ast.Stmt:
        return stmt.replace(
            test=self.rename_expr(stmt.test),
            body=self._rename_stmts(stmt.body),
        )

    def rename_stmt_Pass(self, stmt: ast.Pass) -> ast.Stmt:
        return stmt

    def rename_stmt_Break(self, stmt: ast.Break) -> ast.Stmt:
        return stmt

    def rename_stmt_Continue(self, stmt: ast.Continue) -> ast.Stmt:
        return stmt

    def rename_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> ast.Stmt:
        return stmt.replace(value=self.rename_expr(stmt.value))

    # ---- expressions ----

    def rename_expr_NameLocalDirect(self, expr: ast.NameLocalDirect) -> ast.Expr:
        return expr.replace(sym=self.rename_sym(expr.sym))

    def rename_expr_NameOuterCell(self, expr: ast.NameOuterCell) -> ast.Expr:
        return expr

    def rename_expr_FQNConst(self, expr: ast.FQNConst) -> ast.Expr:
        return expr

    def rename_expr_Literal(self, expr: ast.Literal) -> ast.Expr:
        return expr

    def rename_expr_StrConst(self, expr: ast.StrConst) -> ast.Expr:
        return expr

    def rename_expr_LocConst(self, expr: ast.LocConst) -> ast.Expr:
        return expr

    def rename_expr_And(self, expr: ast.And) -> ast.Expr:
        return expr.replace(
            left=self.rename_expr(expr.left),
            right=self.rename_expr(expr.right),
        )

    def rename_expr_Or(self, expr: ast.Or) -> ast.Expr:
        return expr.replace(
            left=self.rename_expr(expr.left),
            right=self.rename_expr(expr.right),
        )

    def rename_expr_Call(self, expr: ast.Call) -> ast.Expr:
        return expr.replace(
            func=self.rename_expr(expr.func),
            args=[self.rename_expr(a) for a in expr.args],
        )

    def rename_expr_Tuple(self, expr: ast.Tuple) -> ast.Expr:
        return expr.replace(items=[self.rename_expr(i) for i in expr.items])

    def rename_expr_AssignExprLocal(self, expr: ast.AssignExprLocal) -> ast.Expr:
        new_target = expr.target.replace(value=f"{expr.target.value}{self.suffix}")
        return expr.replace(target=new_target, value=self.rename_expr(expr.value))

    def rename_expr_BlockExpr(self, expr: ast.BlockExpr) -> ast.Expr:
        return expr.replace(
            body=self._rename_stmts(expr.body),
            value=self.rename_expr(expr.value),
        )


class InlineResult:
    block: ast.BlockExpr
    new_symbols: list[Symbol]
    new_locals_types_w: "dict[str, W_Type]"

    def __init__(
        self,
        block: ast.BlockExpr,
        new_symbols: list[Symbol],
        new_locals_types_w: "dict[str, W_Type]",
    ) -> None:
        self.block = block
        self.new_symbols = new_symbols
        self.new_locals_types_w = new_locals_types_w


def inline_call(
    vm: "SPyVM",
    op: ast.Node,
    w_callee: W_ASTFunc,
    real_args: list[ast.Expr],
    inline_counter: int,
) -> InlineResult:
    """
    Build a BlockExpr that inlines the callee at the call site.
    w_callee must already be at lowering_stage == "redshift".
    """
    assert w_callee.lowering_stage == "redshift"
    suffix = f"${inline_counter}"

    assert w_callee.locals_types_w is not None
    new_locals_types_w: dict[str, "W_Type"] = {}

    functype = w_callee.w_functype
    funcdef_args = w_callee.funcdef.args
    param_assigns: list[ast.Stmt] = []
    for i, (func_param, funcdef_arg) in enumerate(zip(functype.params, funcdef_args)):
        param_name = funcdef_arg.name
        new_name = f"{param_name}{suffix}"
        new_locals_types_w[new_name] = func_param.w_T

        param_assigns.append(
            ast.AssignLocal(
                loc=op.loc,
                target=ast.StrConst(op.loc, new_name).as_typed_node(),
                value=real_args[i],
            )
        )

    for old_name, w_T in w_callee.locals_types_w.items():
        if old_name.startswith("@"):
            continue  # skip @return and other internal names
        new_name = f"{old_name}{suffix}"
        if new_name not in new_locals_types_w:
            new_locals_types_w[new_name] = w_T

    renamer = AlphaRenamer(w_callee.funcdef, suffix)
    renamed_body = renamer.rename_body()

    last_stmt = renamed_body[-1] if renamed_body else None
    if isinstance(last_stmt, ast.Return):
        stmts_before_return = renamed_body[:-1]
        result_value = last_stmt.value
    else:
        stmts_before_return = renamed_body
        result_value = ast.Literal(op.loc, None, w_T=TYPES.w_NoneType)

    body = [*param_assigns, *stmts_before_return]
    block = ast.BlockExpr(
        loc=op.loc,
        body=body,
        value=result_value,
        w_T=w_callee.w_functype.w_restype,
    )
    return InlineResult(block, renamer.get_new_symbols(), new_locals_types_w)
