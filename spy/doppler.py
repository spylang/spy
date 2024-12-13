from typing import Any, Optional, TYPE_CHECKING
from types import NoneType
from fixedint import FixedInt
from spy import ast
from spy.location import Loc
from spy.fqn import FQN
from spy.errors import SPyTypeError
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type
from spy.vm.function import W_ASTFunc, W_BuiltinFunc, W_Func
from spy.vm.func_adapter import W_FuncAdapter, ArgSpec
from spy.vm.astframe import ASTFrame
from spy.vm.opimpl import W_OpImpl
from spy.vm.modules.operator.convop import CONVERT_maybe
from spy.util import magic_dispatch

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


def redshift(vm: 'SPyVM', w_func: W_ASTFunc) -> W_ASTFunc:
    dop = FuncDoppler(vm, w_func)
    return dop.redshift()


def make_const(vm: 'SPyVM', loc: Loc, w_val: W_Object) -> ast.Expr:
    """
    Create an AST node to represent a constant of the given w_val.

    For primitive types, it's easy, we can just reuse ast.Constant.
    For non primitive types, we assign an unique FQN to the w_val, and we
    return ast.FQNConst.
    """
    w_type = vm.dynamic_type(w_val)
    if w_type in (B.w_i32, B.w_f64, B.w_bool, B.w_void):
        # this is a primitive, we can just use ast.Constant
        value = vm.unwrap(w_val)
        if isinstance(value, FixedInt): # type: ignore
            value = int(value)
        return ast.Constant(loc, value)
    elif w_type is B.w_str:
        value = vm.unwrap_str(w_val)
        return ast.StrConst(loc, value)

    # this is a non-primitive prebuilt constant.
    fqn = vm.make_fqn_const(w_val)
    return ast.FQNConst(loc, fqn)


class FuncDoppler:
    """
    Perform a redshift on a W_ASTFunc
    """

    def __init__(self, vm: 'SPyVM', w_func: W_ASTFunc) -> None:
        self.vm = vm
        self.w_func = w_func
        self.funcdef = w_func.funcdef
        self.blue_frame = ASTFrame(vm, w_func, color='blue')
        self.t = self.blue_frame.t

    def redshift(self) -> W_ASTFunc:
        funcdef = self.w_func.funcdef
        new_body = []
        for stmt in funcdef.body:
            new_body += self.shift_stmt(stmt)
        new_funcdef = funcdef.replace(body=new_body)
        #
        new_fqn = self.w_func.fqn
        # all the non-local lookups are redshifted into constants, so the
        # closure will be empty
        new_closure = ()
        w_newfunctype = self.w_func.w_functype
        w_newfunc = W_ASTFunc(
            fqn = new_fqn,
            closure = new_closure,
            w_functype = w_newfunctype,
            funcdef = new_funcdef,
            locals_types_w = self.t.locals_types_w.copy())
        return w_newfunc

    # =========

    def shift_stmt(self, stmt: ast.Stmt) -> list[ast.Stmt]:
        self.t.check_stmt(stmt)
        return magic_dispatch(self, 'shift_stmt', stmt)

    def shift_expr(self, expr: ast.Expr,
                   *,
                   varname: Optional[str] = None,
                   ) -> ast.Expr:
        wop = self.blue_frame.eval_expr(expr)
        w_typeconv = self.blue_frame.typecheck_maybe(wop, varname)
        if wop.color == 'blue':
            return make_const(self.vm, expr.loc, wop.w_val)
        res = magic_dispatch(self, 'shift_expr', expr)
        if w_typeconv:
            # converters are used only for local variables and if/while
            # conditions (see TypeChecker.expr_conv). Probably we could just
            # use an W_OpImpl instead?
            return ast.Call(
                loc = res.loc,
                func = ast.FQNConst(
                    loc = res.loc,
                    fqn = w_typeconv.fqn
                ),
                args = [res]
            )
        else:
            return res

    # ==== statements ====

    def shift_stmt_Return(self, ret: ast.Return) -> list[ast.Stmt]:
        newvalue = self.shift_expr(ret.value, varname='@return')
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
        self.blue_frame.check_assign_target(assign.target)
        sym = self.funcdef.symtable.lookup(assign.target.value)
        varname = assign.target.value if sym.is_local else None
        if sym.color == 'red':
            newvalue = self.shift_expr(assign.value, varname=varname)
            return [assign.replace(value=newvalue)]
        else:
            assert False, 'implement me'

    def shift_stmt_SetAttr(self, node: ast.SetAttr) -> list[ast.Stmt]:
        v_target = self.shift_expr(node.target)
        v_attr = self.shift_expr(node.attr)
        v_value = self.shift_expr(node.value)
        w_opimpl = self.t.opimpl[node]
        call = self.shift_opimpl(node, w_opimpl, [v_target, v_attr, v_value])
        return [ast.StmtExpr(node.loc, call)]

    def shift_stmt_SetItem(self, node: ast.SetItem) -> list[ast.Stmt]:
        v_target = self.shift_expr(node.target)
        v_index = self.shift_expr(node.index)
        v_value = self.shift_expr(node.value)
        w_opimpl = self.t.opimpl[node]
        call = self.shift_opimpl(node, w_opimpl, [v_target, v_index, v_value])
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
        newtest = self.shift_expr(if_node.test, varname='@if')
        newthen = self.shift_body(if_node.then_body)
        newelse = self.shift_body(if_node.else_body)
        return [if_node.replace(
            test = newtest,
            then_body = newthen,
            else_body = newelse
        )]

    def shift_stmt_While(self, while_node: ast.While) -> list[ast.While]:
        newtest = self.shift_expr(while_node.test, varname='@while')
        newbody = self.shift_body(while_node.body)
        return [while_node.replace(
            test = newtest,
            body = newbody
        )]

    # ==== expressions ====

    def shift_opimpl(self, op: ast.Expr | ast.Stmt,
                     w_opimpl: W_Func,
                     orig_args: list[ast.Expr]
                     ) -> ast.Call:
        assert isinstance(w_opimpl, W_FuncAdapter)
        func = make_const(self.vm, op.loc, w_opimpl.w_func)
        real_args = self._shift_adapter_args(w_opimpl, orig_args)
        return ast.Call(op.loc, func, real_args)

    def _shift_adapter_args(self, w_adapter: W_FuncAdapter,
                            orig_args: list[ast.Expr]) -> list[ast.Expr]:
        real_args = []
        for spec in w_adapter.args:
            if isinstance(spec, ArgSpec.Arg):
                arg = orig_args[spec.i]
                if spec.w_converter is not None:
                    arg = ast.Call(
                        loc = arg.loc,
                        func = ast.FQNConst(
                            loc = arg.loc,
                            fqn = spec.w_converter.fqn
                        ),
                        args = [arg]
                    )
            elif isinstance(spec, ArgSpec.Const):
                arg = make_const(self.vm, spec.loc, spec.w_const)
            else:
                assert False
            real_args.append(arg)
        return real_args

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
        return self.shift_opimpl(binop, w_opimpl, [l, r])

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
        return self.shift_opimpl(op, w_opimpl, [v, i])

    def shift_expr_GetAttr(self, op: ast.GetAttr) -> ast.Expr:
        v = self.shift_expr(op.value)
        v_attr = self.shift_expr(op.attr)
        w_opimpl = self.t.opimpl[op]
        return self.shift_opimpl(op, w_opimpl, [v, v_attr])

    def shift_expr_Call(self, call: ast.Call) -> ast.Expr:
        newfunc = self.shift_expr(call.func)
        newargs = [self.shift_expr(arg) for arg in call.args]
        w_opimpl = self.t.opimpl[call]
        assert isinstance(w_opimpl, W_FuncAdapter)
        if w_opimpl.is_direct_call():
            # sanity check: the redshift MUST have produced a const. If it
            # didn't, the C backend won't be able to compile the call.
            assert isinstance(newfunc, (ast.FQNConst, ast.Constant, ast.StrConst))
            newargs = self._shift_adapter_args(w_opimpl, [newfunc] + newargs)
            newop = ast.Call(call.loc, newfunc, newargs)
            return self.specialize_print_maybe(newop)
        else:
            return self.shift_opimpl(call, w_opimpl, [newfunc] + newargs)

    def specialize_print_maybe(self, call: ast.Call) -> ast.Expr:
        """
        This is a temporary hack. We specialize print() based on the type
        of its first argument
        """
        if not (isinstance(call.func, ast.FQNConst) and
                call.func.fqn == FQN('builtins::print')):
            return call

        assert len(call.args) == 1
        color, w_type = self.t.check_expr(call.args[0])
        t = w_type.fqn.symbol_name
        if w_type in (B.w_i32, B.w_f64, B.w_bool, B.w_void, B.w_str):
            fqn = FQN(f'builtins::print_{t}')
        else:
            raise SPyTypeError(f"Invalid type for print(): {t}")

        newfunc = call.func.replace(fqn=fqn)
        return call.replace(func=newfunc)

    def shift_expr_CallMethod(self, op: ast.CallMethod) -> ast.Expr:
        assert op in self.t.opimpl
        w_opimpl = self.t.opimpl[op]
        v_target = self.shift_expr(op.target)
        v_method = self.shift_expr(op.method)
        newargs_v = [self.shift_expr(arg) for arg in op.args]
        return self.shift_opimpl(op, w_opimpl, [v_target, v_method] + newargs_v)
