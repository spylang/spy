from typing import Any, Optional
from fixedint import FixedInt
from spy import ast
from spy.vm.vm import SPyVM
from spy.vm.function import W_ASTFunc
from spy.vm.astframe import ASTFrame
from spy.util import magic_dispatch


def redshift(vm: SPyVM, w_func: W_ASTFunc) -> W_ASTFunc:
    dop = FuncDoppler(vm, w_func)
    return dop.redshift()

class FuncDoppler:
    """
    Perform a redshift on a W_ASTFunc
    """

    def __init__(self, vm: SPyVM, w_func: W_ASTFunc) -> None:
        self.vm = vm
        self.w_func = w_func
        self.blue_frame = ASTFrame(vm, w_func)

    def redshift(self) -> W_ASTFunc:
        funcdef = self.w_func.funcdef
        new_body = []
        for stmt in funcdef.body:
            new_body += self.shift_stmt(stmt)
        new_funcdef = funcdef.replace(body=new_body)
        #
        new_fqn = self.w_func.fqn # XXX
        new_closure = ()
        w_newfunctype = self.w_func.w_functype
        return W_ASTFunc(
            fqn = new_fqn,
            closure = new_closure,
            w_functype = w_newfunctype,
            funcdef = new_funcdef)

    def blue_eval(self, expr: ast.Expr) -> ast.Constant:
        fv = self.blue_frame.eval_expr(expr)
        # XXX for now we support only primitive contants
        # XXX we should check the type
        # XXX we should propagate the static type somehow?
        value = self.vm.unwrap(fv.w_value)
        if isinstance(value, FixedInt):
            value = int(value)
        return ast.Constant(expr.loc, value)

    # =========

    def shift_stmt(self, stmt: ast.Stmt) -> list[ast.Stmt]:
        return magic_dispatch(self, 'shift_stmt', stmt)

    def shift_expr(self, expr: ast.Expr) -> ast.Expr:
        color, w_type = self.blue_frame.t.check_expr(expr)
        if color == 'blue':
            return self.blue_eval(expr)
        return magic_dispatch(self, 'shift_expr', expr)

    # ==== statements ====

    def shift_stmt_Return(self, ret: ast.Return) -> list[ast.Stmt]:
        newvalue = self.shift_expr(ret.value)
        return [ret.replace(value=newvalue)]

    # ==== expressions ====

    def shift_expr_Constant(self, const: ast.Constant) -> ast.Expr:
        return const

    def shift_expr_BinOp(self, binop: ast.BinOp) -> ast.Expr:
        l = self.shift_expr(binop.left)
        r = self.shift_expr(binop.right)
        return binop.replace(left=l, right=r)

    shift_expr_Add = shift_expr_BinOp
