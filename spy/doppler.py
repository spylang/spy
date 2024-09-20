from typing import Any, Optional, TYPE_CHECKING
from types import NoneType
from fixedint import FixedInt
from spy import ast
from spy.location import Loc
from spy.fqn import FQN
from spy.errors import SPyTypeError
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type
from spy.vm.function import W_ASTFunc, W_BuiltinFunc
from spy.vm.astframe import ASTFrame
from spy.vm.typeconverter import JsRefConv
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

    def redshift(self) -> W_ASTFunc:
        funcdef = self.w_func.funcdef
        new_body = []
        for stmt in funcdef.body:
            new_body += self.shift_stmt(stmt)
        new_funcdef = funcdef.replace(body=new_body)
        #
        new_qn = self.w_func.qn
        # all the non-local lookups are redshifted into constants, so the
        # closure will be empty
        new_closure = ()
        w_newfunctype = self.w_func.w_functype
        w_newfunc = W_ASTFunc(
            qn = new_qn,
            closure = new_closure,
            w_functype = w_newfunctype,
            funcdef = new_funcdef,
            locals_types_w = self.t.locals_types_w.copy())
        return w_newfunc

    def blue_eval(self, expr: ast.Expr) -> ast.Expr:
        w_val = self.blue_frame.eval_expr(expr)
        return self.make_const(expr.loc, w_val)

    def make_const(self, loc: Loc, w_val: W_Object) -> ast.Expr:
        """
        Create an AST node to represent a constant of the given w_val.

        For primitive types, it's easy, we can just reuse ast.Constant.
        For non primitive types, we assign an unique FQN to the w_val, and we
        return ast.FQNConst.
        """
        w_type = self.vm.dynamic_type(w_val)
        if w_type in (B.w_i32, B.w_f64, B.w_bool, B.w_str, B.w_void):
            # this is a primitive, we can just use ast.Constant
            value = self.vm.unwrap(w_val)
            if isinstance(value, FixedInt): # type: ignore
                value = int(value)
            return ast.Constant(loc, value)

        # this is a non-primitive prebuilt constant. If it doesn't have an FQN
        # yet, we need to assign it one. For now we know how to do it only for
        # non-global functions
        fqn = self.vm.reverse_lookup_global(w_val)
        if fqn is None:
            if isinstance(w_val, W_ASTFunc):
                # it's a closure, let's assign it an FQN and add to the globals
                fqn = self.vm.get_FQN(w_val.qn, is_global=False)
                self.vm.add_global(fqn, None, w_val)
            elif isinstance(w_val, W_BuiltinFunc):
                # builtin functions MUST be unique
                fqn = self.vm.get_FQN(w_val.qn, is_global=True)
                self.vm.add_global(fqn, None, w_val)
            else:
                assert False, 'implement me'

        assert fqn is not None
        return ast.FQNConst(loc, fqn)

    # =========

    def shift_stmt(self, stmt: ast.Stmt) -> list[ast.Stmt]:
        self.t.check_stmt(stmt)
        return magic_dispatch(self, 'shift_stmt', stmt)

    def shift_expr(self, expr: ast.Expr) -> ast.Expr:
        color, w_type = self.t.check_expr(expr)
        conv = self.t.expr_conv.get(expr)
        if color == 'blue':
            if not conv or conv.color == 'blue':
                return self.blue_eval(expr)
        res = magic_dispatch(self, 'shift_expr', expr)
        if conv and isinstance(conv, JsRefConv):
            res = conv.redshift(self.vm, res)
        return res

    # ==== statements ====

    def shift_stmt_Return(self, ret: ast.Return) -> list[ast.Stmt]:
        newvalue = self.shift_expr(ret.value)
        return [ret.replace(value=newvalue)]

    def shift_stmt_Pass(self, stmt: ast.Pass) -> list[ast.Stmt]:
        return [stmt]

    def shift_stmt_VarDef(self, vardef: ast.VarDef) -> list[ast.Stmt]:
        ann_color, w_ann_type = self.t.check_expr(vardef.type)
        assert ann_color == 'blue'
        assert isinstance(w_ann_type, W_Type)
        self.blue_frame.exec_stmt_VarDef(vardef)
        newtype = self.shift_expr(vardef.type)
        return [vardef.replace(type=newtype)]

    def shift_stmt_Assign(self, assign: ast.Assign) -> list[ast.Stmt]:
        sym = self.funcdef.symtable.lookup(assign.target)
        if sym.color == 'red':
            newvalue = self.shift_expr(assign.value)
            return [assign.replace(value=newvalue)]
        else:
            assert False, 'implement me'

    def shift_stmt_SetAttr(self, node: ast.SetAttr) -> list[ast.Stmt]:
        v_target = self.shift_expr(node.target)
        v_attr = ast.Constant(node.loc, value=node.attr)
        v_value = self.shift_expr(node.value)
        w_opimpl = self.t.opimpl[node]
        call = self._call_opimpl(node, w_opimpl, [v_target, v_attr, v_value])
        return [ast.StmtExpr(node.loc, call)]

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

    def _call_opimpl(self, op, w_opimpl, orig_args):
        func = self.make_const(op.loc, w_opimpl._w_func)

        new_args = []
        for wv_arg, conv in zip(w_opimpl._args_wv, w_opimpl._converters):
            arg = orig_args[wv_arg.i]
            if conv is not None:
                arg = conv.redshift(self.vm, arg)
            new_args.append(arg)

        return ast.Call(op.loc, func, new_args)

    def shift_expr_Constant(self, const: ast.Constant) -> ast.Expr:
        return const

    def shift_expr_Name(self, name: ast.Name) -> ast.Expr:
        return name

    def shift_expr_List(self, lst: ast.List) -> ast.Expr:
        items = [self.shift_expr(item) for item in lst.items]
        return ast.List(lst.loc, items)

    def shift_expr_BinOp(self, binop: ast.BinOp) -> ast.Expr:
        l = self.shift_expr(binop.left)
        r = self.shift_expr(binop.right)
        w_opimpl = self.t.opimpl[binop]
        return self._call_opimpl(binop, w_opimpl, [l, r])

    shift_expr_Add = shift_expr_BinOp
    shift_expr_Sub = shift_expr_BinOp
    shift_expr_Mul = shift_expr_BinOp
    shift_expr_Div = shift_expr_BinOp
    shift_expr_Eq = shift_expr_BinOp
    shift_expr_NotEq = shift_expr_BinOp
    shift_expr_Lt = shift_expr_BinOp
    shift_expr_LtE = shift_expr_BinOp
    shift_expr_Gt = shift_expr_BinOp
    shift_expr_GtE = shift_expr_BinOp

    def shift_expr_GetItem(self, op: ast.GetItem) -> ast.Expr:
        v = self.shift_expr(op.value)
        i = self.shift_expr(op.index)
        w_opimpl = self.t.opimpl[op]
        return self._call_opimpl(op, w_opimpl, [v, i])

    def shift_expr_GetAttr(self, op: ast.GetAttr) -> ast.Expr:
        v = self.shift_expr(op.value)
        v_attr = ast.Constant(op.loc, value=op.attr)
        w_opimpl = self.t.opimpl[op]
        return self._call_opimpl(op, w_opimpl, [v, v_attr])

    def shift_expr_Call(self, call: ast.Call) -> ast.Expr:
        if call in self.t.opimpl:
            w_opimpl = self.t.opimpl[call]
            # XXX we should shift all the args?
            return self._call_opimpl(call, w_opimpl, [call.func] + call.args)

        newfunc = self.shift_expr(call.func)
        # sanity check: the redshift MUST have produced a const. If it
        # didn't, the C backend won't be able to compile the call.
        assert isinstance(newfunc, (ast.FQNConst, ast.Constant))
        extra_args = []
        newargs = extra_args + [self.shift_expr(arg) for arg in call.args]
        newop = ast.Call(call.loc, newfunc, newargs)
        return self.specialize_print_maybe(newop)

    def specialize_print_maybe(self, call: ast.Call) -> ast.Expr:
        """
        This is a temporary hack. We specialize print() based on the type
        of its first argument
        """
        if not (isinstance(call.func, ast.FQNConst) and
                call.func.fqn == FQN.parse('builtins::print')):
            return call

        assert len(call.args) == 1
        color, w_type = self.t.check_expr(call.args[0])
        t = w_type.name
        if w_type in (B.w_i32, B.w_f64, B.w_bool, B.w_void, B.w_str):
            fqn = FQN.parse(f'builtins::print_{t}')
        else:
            raise SPyTypeError(f"Invalid type for print(): {t}")

        newfunc = call.func.replace(fqn=fqn)
        return call.replace(func=newfunc)

    def shift_expr_CallMethod(self, op: ast.CallMethod) -> ast.Expr:
        assert op in self.t.opimpl
        w_opimpl = self.t.opimpl[op]
        v_target = self.shift_expr(op.target)
        v_method = ast.Constant(op.loc, value=op.method)
        newargs_v = [self.shift_expr(arg) for arg in op.args]
        return self._call_opimpl(op, w_opimpl, [v_target, v_method] + newargs_v)
