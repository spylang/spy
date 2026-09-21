"""
Helpers for @force_inline: validation and inlining mechanics.
"""

from typing import TYPE_CHECKING

from spy import ast
from spy.analyze.symtable import FrameInfo, Symbol
from spy.doppler import make_const
from spy.errors import SPyError
from spy.util import magic_dispatch
from spy.vm.b import B
from spy.vm.function import W_ASTFunc
from spy.vm.primitive import TYPES

if TYPE_CHECKING:
    from spy.vm.object import W_Type
    from spy.vm.vm import SPyVM


def validate_force_inline(w_func: W_ASTFunc) -> None:
    stmts = w_func.funcdef.body.body
    last_stmt = stmts[-1] if stmts else None
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
    Deep-copy a redshifted function body, renaming every callee-local Symbol to a
    fresh slot allocated in the CALLER's FrameInfo (via get_fresh_slot).
    """

    def __init__(self, funcdef: ast.FuncDef, caller_frameinfo: FrameInfo) -> None:
        self.funcdef = funcdef
        self.renamed_syms: dict[Symbol, Symbol] = {}
        self.renamed_slots: dict[str, str] = {}
        for sym in funcdef.frameinfo._symbols.values():
            if not sym.is_local:
                continue
            if sym.src_name.startswith("@"):
                # @-names (@return, @if, ...) are declared/looked up literally at
                # runtime and never mangled; leave them untouched (don't reserve a
                # caller slot, they don't collide).
                self.renamed_syms[sym] = sym
                self.renamed_slots[sym.slot_name] = sym.slot_name
                continue
            # alpha-rename the callee locals into the caller frameinfo
            new_slot_name = caller_frameinfo.get_fresh_slot(sym.src_name)
            new_sym = sym.replace(slot_name=new_slot_name)
            self.renamed_syms[sym] = new_sym
            self.renamed_slots[sym.slot_name] = new_slot_name
            caller_frameinfo.add(new_sym)

    def rename_body(self) -> list[ast.Stmt]:
        return self._rename_stmts(self.funcdef.body.body)

    def _rename_stmts(self, stmts: list[ast.Stmt]) -> list[ast.Stmt]:
        return [self.rename_stmt(s) for s in stmts]

    def _rename_block(self, block: ast.Block) -> ast.Block:
        return block.replace(body=self._rename_stmts(block.body))

    def rename_stmt(self, stmt: ast.Stmt) -> ast.Stmt:
        return magic_dispatch(self, "rename_stmt", stmt)

    def rename_expr(self, expr: ast.Expr) -> ast.Expr:
        return magic_dispatch(self, "rename_expr", expr)

    # ---- statements ----

    def rename_stmt_Return(self, stmt: ast.Return) -> ast.Stmt:
        return stmt.replace(value=self.rename_expr(stmt.value))

    def rename_stmt_VarDef(self, stmt: ast.VarDef) -> ast.Stmt:
        new_sym = self.renamed_syms[stmt.sym]
        new_name_node = stmt.name.replace(value=new_sym.slot_name)
        new_value = self.rename_expr(stmt.value) if stmt.value is not None else None
        # the runtime slot is taken from _sym.slot_name, so rename the sym too
        return stmt.replace(
            name=new_name_node,
            value=new_value,
            _sym=new_sym,
        )

    def rename_stmt_AssignLocal(self, stmt: ast.AssignLocal) -> ast.Stmt:
        return stmt.replace(expr=self.rename_expr(stmt.expr))

    def rename_stmt_AssignCell(self, stmt: ast.AssignCell) -> ast.Stmt:
        return stmt.replace(expr=self.rename_expr(stmt.expr))

    def rename_expr_AssignExprCell(self, expr: ast.AssignExprCell) -> ast.Expr:
        return expr.replace(value=self.rename_expr(expr.value))

    def rename_stmt_If(self, stmt: ast.If) -> ast.Stmt:
        return stmt.replace(
            test=self.rename_expr(stmt.test),
            then=self._rename_block(stmt.then),
            else_=self._rename_block(stmt.else_),
        )

    def rename_stmt_While(self, stmt: ast.While) -> ast.Stmt:
        return stmt.replace(
            test=self.rename_expr(stmt.test),
            body=self._rename_block(stmt.body),
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
        return expr.replace(sym=self.renamed_syms[expr.sym])

    def rename_expr_NameOuterCell(self, expr: ast.NameOuterCell) -> ast.Expr:
        return expr

    def rename_expr_FQNConst(self, expr: ast.FQNConst) -> ast.Expr:
        return expr

    def rename_expr_Const(self, expr: ast.Const) -> ast.Expr:
        return expr

    def rename_expr_Literal(self, expr: ast.Literal) -> ast.Expr:
        return expr

    def rename_expr_StrLiteral(self, expr: ast.StrLiteral) -> ast.Expr:
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
        new_sym = self.renamed_syms[expr.sym]
        new_target = expr.target.replace(value=new_sym.slot_name)
        return expr.replace(
            target=new_target,
            sym=new_sym,
            value=self.rename_expr(expr.value),
        )

    def rename_expr_BlockExpr(self, expr: ast.BlockExpr) -> ast.Expr:
        return expr.replace(
            body=self._rename_stmts(expr.body),
            value=self.rename_expr(expr.value),
        )


class InlineResult:
    block: ast.BlockExpr
    new_locals_types_w: "dict[str, W_Type]"

    def __init__(
        self,
        block: ast.BlockExpr,
        new_locals_types_w: "dict[str, W_Type]",
    ) -> None:
        self.block = block
        self.new_locals_types_w = new_locals_types_w


def inline_call(
    vm: "SPyVM",
    caller_op: ast.Node,
    caller_frameinfo: FrameInfo,
    w_callee: W_ASTFunc,
    real_args: list[ast.Expr],
) -> InlineResult:
    """
    Build a BlockExpr that inlines the callee at the call site.
    w_callee must already be at stage == "redshifted".

    Variables used by the callee are alpha-renamed and placed into caller_frameinfo.
    """
    assert w_callee.stage == "redshifted"

    assert w_callee.locals_types_w is not None
    new_locals_types_w: dict[str, "W_Type"] = {}

    functype = w_callee.w_functype
    funcdef_args = w_callee.funcdef.args

    renamer = AlphaRenamer(w_callee.funcdef, caller_frameinfo)
    renamed_slots = renamer.renamed_slots

    param_assigns: list[ast.Stmt] = []
    for i, (func_param, funcdef_arg) in enumerate(zip(functype.params, funcdef_args)):
        old_slot_name = funcdef_arg.sym.slot_name
        new_slot_name = renamed_slots[old_slot_name]
        new_locals_types_w[new_slot_name] = func_param.w_T
        param_sym = renamer.renamed_syms[funcdef_arg.sym]

        param_assigns.append(
            ast.AssignLocal(
                loc=caller_op.loc,
                expr=ast.AssignExprLocal(
                    loc=caller_op.loc,
                    target=ast.StrLiteral(caller_op.loc, new_slot_name).as_typed_node(),
                    sym=param_sym,
                    value=real_args[i],
                    w_T=func_param.w_T,
                ),
            )
        )

    for old_slot_name, w_T in w_callee.locals_types_w.items():
        if old_slot_name.startswith("@"):
            continue  # skip @return and other internal names
        new_slot_name = renamed_slots[old_slot_name]
        if new_slot_name not in new_locals_types_w:
            new_locals_types_w[new_slot_name] = w_T

    renamed_body = renamer.rename_body()

    last_stmt = renamed_body[-1] if renamed_body else None
    if isinstance(last_stmt, ast.Return):
        stmts_before_return = renamed_body[:-1]
        result_value = last_stmt.value
    else:
        stmts_before_return = renamed_body
        result_value = ast.Const(caller_op.loc, B.w_None, w_T=TYPES.w_NoneType)

    body = [*param_assigns, *stmts_before_return]
    block = ast.BlockExpr(
        loc=caller_op.loc,
        body=body,
        value=result_value,
        w_T=w_callee.w_functype.w_restype,
    )
    return InlineResult(block, new_locals_types_w)
