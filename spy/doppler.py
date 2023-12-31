from typing import Any, Optional, TYPE_CHECKING
from types import NoneType
from fixedint import FixedInt
from spy import ast
from spy.vm.builtins import B
from spy.vm.object import W_Object
from spy.vm.function import W_ASTFunc
from spy.vm.astframe import ASTFrame
from spy.util import magic_dispatch

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


def redshift(vm: 'SPyVM', w_func: W_ASTFunc) -> W_ASTFunc:
    dop = FuncDoppler(vm, w_func)
    return dop.redshift()

class FuncDoppler:
    """
    Perform a redshift on a W_ASTFunc
    """

    def __init__(self, vm: 'SPyVM', w_func: W_ASTFunc) -> None:
        self.vm = vm
        self.w_func = w_func
        self.funcdef = w_func.funcdef
        self.blue_frame = ASTFrame(vm, w_func)
        self.t = self.blue_frame.t
        self.blue_frame.declare_arguments()

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
        w_newfunc = W_ASTFunc(
            fqn = new_fqn,
            closure = new_closure,
            w_functype = w_newfunctype,
            funcdef = new_funcdef,
            locals_types_w = self.t.locals_types_w.copy())
        return w_newfunc

    def blue_eval(self, expr: ast.Expr) -> ast.Expr:
        fv = self.blue_frame.eval_expr(expr)
        # XXX we should check the type
        # XXX we should propagate the static type somehow?
        w_type = fv.w_static_type
        if w_type in (B.w_i32, B.w_bool, B.w_str, B.w_void):
            # this is a primitive, we can just use ast.Constant
            value = self.vm.unwrap(fv.w_value)
            if isinstance(value, FixedInt): # type: ignore
                value = int(value)
            return ast.Constant(expr.loc, value)
        else:
            # this is a non-primitive prebuilt constant. For now we support
            # only objects which has a FQN (e.g., builtin types), but we need
            # to think about a more general solution
            fqn = self.vm.reverse_lookup_global(fv.w_value)
            assert fqn is not None, 'implement me'
            return ast.FQNConst(expr.loc, fqn)

    # =========

    def shift_stmt(self, stmt: ast.Stmt) -> list[ast.Stmt]:
        self.t.check_stmt(stmt)
        return magic_dispatch(self, 'shift_stmt', stmt)

    def shift_expr(self, expr: ast.Expr) -> ast.Expr:
        color, w_type = self.t.check_expr(expr)
        if color == 'blue':
            return self.blue_eval(expr)
        return magic_dispatch(self, 'shift_expr', expr)

    # ==== statements ====

    def shift_stmt_Return(self, ret: ast.Return) -> list[ast.Stmt]:
        newvalue = self.shift_expr(ret.value)
        return [ret.replace(value=newvalue)]

    def shift_stmt_VarDef(self, vardef: ast.VarDef) -> list[ast.Stmt]:
        assert vardef.value is not None
        sym = self.blue_frame.declare_VarDef(vardef)
        assert sym.is_local
        if sym.color == 'red':
            newvalue = self.shift_expr(vardef.value)
            newtype = self.shift_expr(vardef.type)
            return [vardef.replace(value=newvalue, type=newtype)]
        else:
            assert False, 'implement me'

    def shift_stmt_Assign(self, assign: ast.Assign) -> list[ast.Stmt]:
        sym = self.funcdef.symtable.lookup(assign.target)
        if sym.is_local and assign.target not in self.t.locals_types_w:
            # XXX fix me
            raise NotImplementedError('redshift of implicit declarations')
        elif sym.color == 'red':
            newvalue = self.shift_expr(assign.value)
            return [assign.replace(value=newvalue)]
        else:
            assert False, 'implement me'

    def shift_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> list[ast.Stmt]:
        newvalue = self.shift_expr(stmt.value)
        return [stmt.replace(value=newvalue)]

    def shift_body(self, body: list[ast.Stmt]) -> list[ast.Stmt]:
        newbody = []
        for stmt in body:
            newbody += self.shift_stmt(stmt)
        return newbody

    def shift_stmt_If(self, if_node: ast.If) -> list[ast.Stmt]:
        newtest = self.shift_expr(if_node.test)
        newthen = self.shift_body(if_node.then_body)
        newelse = self.shift_body(if_node.else_body)
        return [if_node.replace(
            test = newtest,
            then_body = newthen,
            else_body = newelse
        )]

    def shift_stmt_While(self, while_node: ast.While) -> list[ast.While]:
        newtest = self.shift_expr(while_node.test)
        newbody = self.shift_body(while_node.body)
        return [while_node.replace(
            test = newtest,
            body = newbody
        )]

    # ==== expressions ====

    def shift_expr_Constant(self, const: ast.Constant) -> ast.Expr:
        return const

    def shift_expr_Name(self, name: ast.Name) -> ast.Expr:
        return name

    def shift_expr_BinOp(self, binop: ast.BinOp) -> ast.Expr:
        l = self.shift_expr(binop.left)
        r = self.shift_expr(binop.right)
        return binop.replace(left=l, right=r)

    shift_expr_Add = shift_expr_BinOp
    shift_expr_Sub = shift_expr_BinOp
    shift_expr_Mul = shift_expr_BinOp
    shift_expr_Div = shift_expr_BinOp

    def shift_expr_CompareOp(self, cmpop: ast.CompareOp) -> ast.Expr:
        l = self.shift_expr(cmpop.left)
        r = self.shift_expr(cmpop.right)
        return cmpop.replace(left=l, right=r)

    shift_expr_Eq = shift_expr_CompareOp
    shift_expr_NotEq = shift_expr_CompareOp
    shift_expr_Lt = shift_expr_CompareOp
    shift_expr_LtE = shift_expr_CompareOp
    shift_expr_Gt = shift_expr_CompareOp
    shift_expr_GtE = shift_expr_CompareOp

    def shift_expr_Call(self, call: ast.Call) -> ast.Expr:
        # XXX: this assumes that it's a direct call (i.e., call.func is a
        # ast.Name). We probably need to adapt for indirect calls, when we
        # support them
        newfunc = self.shift_expr(call.func)
        newargs = [self.shift_expr(arg) for arg in call.args]
        return call.replace(func=newfunc, args=newargs)
