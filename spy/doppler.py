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
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.modules.operator.convop import CONVERT_maybe
from spy.util import magic_dispatch

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


def redshift(vm: 'SPyVM', w_func: W_ASTFunc) -> W_ASTFunc:
    dop = DopplerFrame(vm, w_func)
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


class DopplerFrame(ASTFrame):
    """
    Perform redshift on a W_ASTFunc
    """
    shifted_expr: dict[ast.Expr, ast.Expr]
    opimpl: dict[ast.Node, W_Func]

    def __init__(self, vm: 'SPyVM', w_func: W_ASTFunc) -> None:
        super().__init__(vm, w_func)
        self.shifted_expr = {}
        self.opimpl = {}

    # overridden
    @property
    def redshifting(self) -> bool:
        return True

    def redshift(self) -> W_ASTFunc:
        self.declare_arguments()
        funcdef = self.w_func.funcdef
        new_body = []
        # fwdecl of types
        for stmt in funcdef.body:
            if isinstance(stmt, ast.ClassDef):
                self.fwdecl_ClassDef(stmt)

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
            locals_types_w = self.locals_types_w.copy())
        return w_newfunc

    # =========

    # ==== statements ====

    def shift_stmt(self, stmt: ast.Stmt) -> list[ast.Stmt]:
        return magic_dispatch(self, 'shift_stmt', stmt)

    def shift_stmt_Return(self, ret: ast.Return) -> list[ast.Stmt]:
        newvalue = self.eval_and_shift(ret.value, varname='@return')
        return [ret.replace(value=newvalue)]

    def shift_stmt_Pass(self, stmt: ast.Pass) -> list[ast.Stmt]:
        return [stmt]

    def shift_stmt_VarDef(self, vardef: ast.VarDef) -> list[ast.Stmt]:
        self.exec_stmt_VarDef(vardef)
        newtype = self.shifted_expr[vardef.type]
        return [vardef.replace(type=newtype)]

    def shift_stmt_Assign(self, assign: ast.Assign) -> list[ast.Stmt]:
        self.exec_stmt_Assign(assign)
        newvalue = self.shifted_expr[assign.value]
        return [assign.replace(value=newvalue)]

    def shift_stmt_SetAttr(self, node: ast.SetAttr) -> list[ast.Stmt]:
        self.exec_stmt(node)
        w_opimpl = self.opimpl[node]
        v_target = self.shifted_expr[node.target]
        v_attr = self.shifted_expr[node.attr]
        v_value = self.shifted_expr[node.value]
        call = self.shift_opimpl(node, w_opimpl, [v_target, v_attr, v_value])
        return [ast.StmtExpr(node.loc, call)]

    def shift_stmt_SetItem(self, node: ast.SetItem) -> list[ast.Stmt]:
        self.exec_stmt(node)
        w_opimpl = self.opimpl[node]
        v_target = self.shifted_expr[node.target]
        v_index = self.shifted_expr[node.index]
        v_value = self.shifted_expr[node.value]
        call = self.shift_opimpl(node, w_opimpl, [v_target, v_index, v_value])
        return [ast.StmtExpr(node.loc, call)]

    def shift_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> list[ast.Stmt]:
        newvalue = self.eval_and_shift(stmt.value)
        return [stmt.replace(value=newvalue)]

    def shift_body(self, body: list[ast.Stmt]) -> list[ast.Stmt]:
        newbody = []
        for stmt in body:
            newbody += self.shift_stmt(stmt)
        return newbody

    def shift_stmt_If(self, if_node: ast.If) -> list[ast.Stmt]:
        newtest = self.eval_and_shift(if_node.test, varname='@if')
        newthen = self.shift_body(if_node.then_body)
        newelse = self.shift_body(if_node.else_body)
        return [if_node.replace(
            test = newtest,
            then_body = newthen,
            else_body = newelse
        )]

    def shift_stmt_While(self, while_node: ast.While) -> list[ast.While]:
        newtest = self.eval_and_shift(while_node.test, varname='@while')
        newbody = self.shift_body(while_node.body)
        return [while_node.replace(
            test = newtest,
            body = newbody
        )]

    # ==== expressions ====

    def eval_and_shift(self, expr: ast.Expr,
                       *,
                       varname: Optional[str] = None,
                       ) -> ast.Expr:
        """
        Just a shortcut to call eval_expr() and get its shifted version.
        """
        self.eval_expr(expr, varname=varname)
        return self.shifted_expr[expr]

    def eval_expr(self, expr: ast.Expr,
                  *,
                  varname: Optional[str] = None,
                  ) -> W_OpArg:
        """
        Override ASTFrame.eval_expr.
        For each expr, also compute its shifted version.

        The execution flow is a bit of a ping-pong between astframe and
        doppler. It is better explained by tracing what happens when shifting
        a statement like "return 1 + 3":

        FuncDoppler.shift_stmt_Return
          -> call self.eval_and_shift(ret.value)

          FuncDoppler.eval_and_shift
            -> call self.eval_expr
            -> return self.shifted_expr[...]

            FuncDoppler.eval_expr
              -> call ASTFrame.eval_expr
              -> call FuncDoppler.shift_expr

              ASTFrame.eval_expr_BinOp
                -> recursive call eval_expr() on binop.{left,right}
                -> call FuncDoppler.eval_opimpl

                FuncDoppler.eval_opimpl
                  -> save self.opimpl[op]
                  -> call ASTFrame.eval_opimpl
                  -> return W_OpArg

              FuncDoppler.shift_expr_BinOp
                  -> retrieve shifted operands for binop.{left,right}
                  -> compute shited binop (stored in .shifted_expr)
        """
        wop = super().eval_expr(expr, varname=varname)
        if wop.color == 'blue':
            new_expr = make_const(self.vm, expr.loc, wop.w_val)
        else:
            new_expr = self.shift_expr(expr)

        w_typeconv = self.typecheck_maybe(wop, varname)
        if w_typeconv:
            new_expr = ast.Call(
                loc = new_expr.loc,
                func = ast.FQNConst(
                    loc = new_expr.loc,
                    fqn = w_typeconv.fqn
                ),
                args = [new_expr]
            )

        self.shifted_expr[expr] = new_expr
        return wop

    def eval_opimpl(self, op: ast.Node, w_opimpl: W_Func,
                    args_wop: list[W_OpArg]) -> W_OpArg:
        """
        Override ASTFrame.eval_opimpl.
        This is a bug ugly, but too bad: record a mapping from op to w_opimpl.
        """
        self.opimpl[op] = w_opimpl
        return super().eval_opimpl(op, w_opimpl, args_wop)

    def shift_expr(self, expr: ast.Expr) -> ast.Expr:
        """
        Shift an expression and store it into self.shifted_expr.

        This method must to be called EXACTLY ONCE for each expr node
        of the AST, and it's supposed to be called by eval_expr.
        """
        assert expr not in self.shifted_expr
        new_expr = magic_dispatch(self, 'shift_expr', expr)
        self.shifted_expr[expr] = new_expr
        return new_expr

    def shift_opimpl(self, op: ast.Node,
                     w_opimpl: W_Func,
                     orig_args: list[ast.Expr]
                     ) -> ast.Call:
        assert isinstance(w_opimpl, W_FuncAdapter)
        func = make_const(self.vm, op.loc, w_opimpl.w_func)
        real_args = self._shift_adapter_args(w_opimpl, orig_args)
        return ast.Call(op.loc, func, real_args)

    def _shift_adapter_args(self, w_adapter: W_FuncAdapter,
                            orig_args: list[ast.Expr]) -> list[ast.Expr]:
        def getarg(spec: ArgSpec) -> ast.Expr:
            if isinstance(spec, ArgSpec.Arg):
                return orig_args[spec.i]
            elif isinstance(spec, ArgSpec.Const):
                return make_const(self.vm, spec.loc, spec.w_const)
            elif isinstance(spec, ArgSpec.Convert):
                arg = getarg(spec.arg)
                return ast.Call(
                    loc = arg.loc,
                    func = ast.FQNConst(
                        loc = arg.loc,
                        fqn = spec.w_conv.fqn
                    ),
                    args = [arg]
                )
            else:
                assert False
        real_args = [getarg(spec) for spec in w_adapter.args]
        return real_args

    def shift_expr_Constant(self, const: ast.Constant) -> ast.Expr:
        return const

    def shift_expr_Name(self, name: ast.Name) -> ast.Expr:
        return name

    def shift_expr_BinOp(self, binop: ast.BinOp) -> ast.Expr:
        w_opimpl = self.opimpl[binop]
        l = self.shifted_expr[binop.left]
        r = self.shifted_expr[binop.right]
        return self.shift_opimpl(binop, w_opimpl, [l, r])

    shift_expr_Add = shift_expr_BinOp
    shift_expr_Sub = shift_expr_BinOp
    shift_expr_Mul = shift_expr_BinOp
    shift_expr_Div = shift_expr_BinOp
    shift_expr_Mod = shift_expr_BinOp
    shift_expr_Eq = shift_expr_BinOp
    shift_expr_NotEq = shift_expr_BinOp
    shift_expr_Lt = shift_expr_BinOp
    shift_expr_LtE = shift_expr_BinOp
    shift_expr_Gt = shift_expr_BinOp
    shift_expr_GtE = shift_expr_BinOp

    def shift_expr_List(self, lst: ast.List) -> ast.Expr:
        items = [self.shifted_expr[item] for item in lst.items]
        return ast.List(lst.loc, items)

    def shift_expr_GetItem(self, op: ast.GetItem) -> ast.Expr:
        w_opimpl = self.opimpl[op]
        v = self.shifted_expr[op.value]
        i = self.shifted_expr[op.index]
        return self.shift_opimpl(op, w_opimpl, [v, i])

    def shift_expr_GetAttr(self, op: ast.GetAttr) -> ast.Expr:
        w_opimpl = self.opimpl[op]
        v = self.shifted_expr[op.value]
        v_attr = self.shifted_expr[op.attr]
        return self.shift_opimpl(op, w_opimpl, [v, v_attr])

    def shift_expr_Call(self, call: ast.Call) -> ast.Expr:
        w_opimpl = self.opimpl[call]
        newfunc = self.shifted_expr[call.func]
        newargs = [self.shifted_expr[arg] for arg in call.args]
        newcall = self.shift_opimpl(call, w_opimpl, [newfunc] + newargs)
        if (isinstance(newcall.func, ast.FQNConst) and
            newcall.func.fqn == FQN('builtins::print')):
            return self.specialize_print(w_opimpl, newcall)
        return newcall

    def specialize_print(self, w_opimpl: W_Func, call: ast.Call) -> ast.Expr:
        """
        This is a temporary hack. We specialize print() based on the type
        of its first argument
        """
        assert len(call.args) == 1
        w_argtype = w_opimpl.w_functype.params[1].w_type
        t = w_argtype.fqn.symbol_name
        if w_argtype in (B.w_i32, B.w_f64, B.w_bool, B.w_void, B.w_str):
            fqn = FQN(f'builtins::print_{t}')
        else:
            raise SPyTypeError(f"Invalid type for print(): {t}")

        newfunc = call.func.replace(fqn=fqn)
        return call.replace(func=newfunc)

    def shift_expr_CallMethod(self, op: ast.CallMethod) -> ast.Expr:
        w_opimpl = self.opimpl[op]
        v_obj = self.shifted_expr[op.target]
        v_meth = self.shifted_expr[op.method]
        newargs_v = [self.shifted_expr[arg] for arg in op.args]
        return self.shift_opimpl(op, w_opimpl, [v_obj, v_meth] + newargs_v)
