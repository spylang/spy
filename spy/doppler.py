from typing import TYPE_CHECKING, Literal, Optional

from fixedint import FixedInt

from spy import ast
from spy.analyze.symtable import Color
from spy.errors import SPyError
from spy.fqn import FQN
from spy.location import Loc
from spy.util import magic_dispatch
from spy.vm.astframe import ASTFrame
from spy.vm.b import B
from spy.vm.exc import W_StaticError
from spy.vm.function import W_ASTFunc, W_Func
from spy.vm.modules.__spy__ import SPY
from spy.vm.modules.types import TYPES, W_Loc
from spy.vm.object import W_Object
from spy.vm.opimpl import ArgSpec, W_OpImpl
from spy.vm.opspec import W_MetaArg
from spy.vm.tuple import W_Tuple

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

ErrorMode = Literal["eager", "lazy", "warn"]


def redshift(vm: "SPyVM", w_func: W_ASTFunc, error_mode: ErrorMode) -> W_ASTFunc:
    dop = DopplerFrame(vm, w_func, error_mode)
    return dop.redshift()


def make_const(vm: "SPyVM", loc: Loc, w_val: W_Object) -> ast.Expr:
    """
    Create an AST node to represent a constant of the given w_val.

    For primitive types, it's easy, we can just reuse ast.Constant.
    For non primitive types, we assign an unique FQN to the w_val, and we
    return ast.FQNConst.
    """
    w_T = vm.dynamic_type(w_val)
    if w_T in (B.w_i32, B.w_f64, B.w_bool, TYPES.w_NoneType):
        # this is a primitive, we can just use ast.Constant
        value = vm.unwrap(w_val)
        if isinstance(value, FixedInt):  # type: ignore
            value = int(value)
        return ast.Constant(loc, value)

    elif w_T is B.w_str:
        value = vm.unwrap_str(w_val)
        return ast.StrConst(loc, value)

    elif w_T is B.w_tuple:
        assert isinstance(w_val, W_Tuple)
        items = [make_const(vm, loc, w_item) for w_item in w_val.items_w]
        return ast.Tuple(loc, items)

    elif w_T is TYPES.w_Loc:
        # note that here we have two locs: 'loc' is as usual the location
        # where the const comes from; 'value' is the actual value of the
        # const, which happen to be of type Loc.
        assert isinstance(w_val, W_Loc)
        value = w_val.loc
        return ast.LocConst(loc, value)

    # this is a non-primitive prebuilt constant.
    fqn = vm.make_fqn_const(w_val)
    return ast.FQNConst(loc, fqn)


class DopplerFrame(ASTFrame):
    """
    Perform redshift on a W_ASTFunc
    """

    shifted_expr: dict[ast.Expr, ast.Expr]
    opimpl: dict[ast.Node, W_OpImpl]
    error_mode: ErrorMode

    def __init__(self, vm: "SPyVM", w_func: W_ASTFunc, error_mode: ErrorMode) -> None:
        assert w_func.color == "red"
        super().__init__(vm, w_func, args_w=None)
        self.shifted_expr = {}
        self.opimpl = {}
        assert error_mode != "warn"
        self.error_mode = error_mode

    # overridden
    @property
    def redshifting(self) -> bool:
        return True

    def redshift(self) -> W_ASTFunc:
        assert not self.w_func.redshifted, "cannot redshit twice"
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
            fqn=new_fqn,
            closure=new_closure,
            w_functype=w_newfunctype,
            funcdef=new_funcdef,
            locals_types_w=self.get_locals_types_w(),
        )
        # mark the original function as invalid
        self.w_func.invalidate(w_newfunc)
        return w_newfunc

    # =========

    # ==== statements ====

    def shift_stmt(self, stmt: ast.Stmt) -> list[ast.Stmt]:
        try:
            return magic_dispatch(self, "shift_stmt", stmt)
        except SPyError as err:
            if self.error_mode == "lazy" and err.match(W_StaticError):
                # turn the exception into a lazy "raise" statement
                self.vm.emit_warning(err)
                return self.make_raise_from_SPyError(stmt, err)
            else:
                # else, just raise the exception as usual
                raise

    def make_raise_from_SPyError(self, stmt: ast.Stmt, err: SPyError) -> list[ast.Stmt]:
        """
        Turn the given stmt into a "raise"
        """
        fqn = self.vm.make_fqn_const(err.w_exc)
        exc = ast.FQNConst(fqn=fqn, loc=stmt.loc)
        return self.shift_stmt(ast.Raise(exc=exc, loc=stmt.loc))

    def record_node_color(self, node: ast.Node, color: Color) -> None:
        if self.vm.ast_color_map is not None:
            self.vm.ast_color_map[node] = color

    def shift_stmt_Return(self, ret: ast.Return) -> list[ast.Stmt]:
        newvalue = self.eval_and_shift(ret.value, varname="@return")
        return [ret.replace(value=newvalue)]

    def shift_stmt_Pass(self, stmt: ast.Pass) -> list[ast.Stmt]:
        return [stmt]

    def shift_stmt_Break(self, stmt: ast.Break) -> list[ast.Stmt]:
        return [stmt]

    def shift_stmt_Continue(self, stmt: ast.Continue) -> list[ast.Stmt]:
        return [stmt]

    def shift_stmt_VarDef(self, vardef: ast.VarDef) -> list[ast.Stmt]:
        varname = vardef.name.value
        is_auto = isinstance(vardef.type, ast.Auto)
        self.exec_stmt_VarDef(vardef)

        sym = self.symtable.lookup(varname)
        assert sym.is_local
        if self.locals[varname].color == "blue":
            # redshift away assignments to blue locals
            return []

        if is_auto:
            # use the actual type computed during type inference
            w_T = self.locals[varname].w_T
            newtype = make_const(self.vm, vardef.type.loc, w_T)
        else:
            newtype = self.shifted_expr[vardef.type]

        if vardef.value is None:
            newvalue = None
        else:
            newvalue = self.shifted_expr[vardef.value]
        return [vardef.replace(type=newtype, value=newvalue)]

    def shift_stmt_Assign(self, assign: ast.Assign) -> list[ast.Stmt]:
        self.exec_stmt_Assign(assign)
        varname = assign.target.value
        sym = self.symtable.lookup(varname)
        if sym.is_local and self.locals[varname].color == "blue":
            self.record_node_color(assign, "blue")
            # redshift away assignments to blue locals
            return []
        else:
            if sym.is_local:
                self.record_node_color(assign, self.locals[varname].color)
            specialized = self.specialized_assigns[assign]
            newvalue = self.shifted_expr[assign.value]
            return [specialized.replace(value=newvalue)]

    def shift_stmt_AssignLocal(self, assign: ast.AssignLocal) -> list[ast.Stmt]:
        # specialized stmts such as AssignLocal and AssignCell are present
        # ONLY inside redshifted ASTs, so we should never see them here
        assert False, "not supposed to happen"

    def shift_stmt_AssignCell(self, assign: ast.AssignCell) -> list[ast.Stmt]:
        # specialized stmts such as AssignLocal and AssignCell are present
        # ONLY inside redshifted ASTs, so we should never see them here
        assert False, "not supposed to happen"

    def shift_stmt_AugAssign(self, node: ast.AugAssign) -> list[ast.Stmt]:
        assign = self._desugar_AugAssign(node)
        return self.shift_stmt_Assign(assign)

    def shift_stmt_UnpackAssign(self, unpack: ast.UnpackAssign) -> list[ast.Stmt]:
        self.exec_stmt_UnpackAssign(unpack)
        newvalue = self.shifted_expr[unpack.value]
        return [unpack.replace(value=newvalue)]

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
        args_v = [self.shifted_expr[arg] for arg in node.args]
        v_value = self.shifted_expr[node.value]
        call = self.shift_opimpl(node, w_opimpl, [v_target] + args_v + [v_value])
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
        newtest = self.eval_and_shift(if_node.test, varname="@if")
        newthen = self.shift_body(if_node.then_body)
        newelse = self.shift_body(if_node.else_body)
        return [if_node.replace(test=newtest, then_body=newthen, else_body=newelse)]

    def shift_stmt_While(self, while_node: ast.While) -> list[ast.Stmt]:
        newtest = self.eval_and_shift(while_node.test, varname="@while")
        newbody = self.shift_body(while_node.body)
        return [while_node.replace(test=newtest, body=newbody)]

    def shift_stmt_For(self, for_node: ast.For) -> list[ast.Stmt]:
        init_iter, while_loop = self._desugar_For(for_node)
        return self.shift_stmt(init_iter) + self.shift_stmt(while_loop)

    def shift_stmt_Raise(self, raise_node: ast.Raise) -> list[ast.Stmt]:
        self.exec_stmt(raise_node)
        w_opimpl = self.opimpl[raise_node]
        v_exc = self.shifted_expr[raise_node.exc]
        call = self.shift_opimpl(raise_node, w_opimpl, [v_exc])
        return [ast.StmtExpr(raise_node.loc, call)]

    def shift_stmt_Assert(self, assert_node: ast.Assert) -> list[ast.Stmt]:
        new_test = self.eval_and_shift(assert_node.test, varname="@assert")
        new_msg = None

        if assert_node.msg is not None:
            wam_msg = self.eval_expr(assert_node.msg)

            if wam_msg.w_static_T is not B.w_str:
                err = SPyError("W_TypeError", "mismatched types")
                err.add(
                    "error",
                    f"expected `str`, got `{wam_msg.w_static_T.fqn.human_name}`",
                    loc=wam_msg.loc,
                )
                raise err

            new_msg = self.shifted_expr[assert_node.msg]

        return [assert_node.replace(test=new_test, msg=new_msg)]

    # ==== expressions ====

    def eval_and_shift(
        self,
        expr: ast.Expr,
        *,
        varname: Optional[str] = None,
    ) -> ast.Expr:
        """
        Just a shortcut to call eval_expr() and get its shifted version.
        """
        self.eval_expr(expr, varname=varname)
        return self.shifted_expr[expr]

    def eval_expr(
        self,
        expr: ast.Expr,
        *,
        varname: Optional[str] = None,
    ) -> W_MetaArg:
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
              -> call eval_expr_*
              -> call shift_expr_*

              ASTFrame.eval_expr_BinOp
                -> recursive call eval_expr() on binop.{left,right}
                -> call FuncDoppler.eval_opimpl

                FuncDoppler.eval_opimpl
                  -> save self.opimpl[op]
                  -> call ASTFrame.eval_opimpl
                  -> return W_MetaArg

              FuncDoppler.shift_expr_BinOp
                  -> retrieve shifted operands for binop.{left,right}
                  -> compute shited binop (stored in .shifted_expr)
        """
        assert self.redshifting
        wam = magic_dispatch(self, "eval_expr", expr)
        new_expr = self.shift_expr(expr, wam)

        w_typeconv_opimpl = self.typecheck_maybe(wam, varname)
        if w_typeconv_opimpl:
            assert varname is not None
            lv = self.locals[varname]
            expT = make_const(self.vm, lv.decl_loc, lv.w_T)
            gotT = make_const(self.vm, wam.loc, wam.w_static_T)
            new_expr = self.shift_opimpl(
                expr, w_typeconv_opimpl, [expT, gotT, new_expr]
            )

        self.shifted_expr[expr] = new_expr
        self.record_node_color(expr, wam.color)
        return wam

    def eval_opimpl(
        self, op: ast.Node, w_opimpl: W_OpImpl, args_wam: list[W_MetaArg]
    ) -> W_MetaArg:
        """
        Override ASTFrame.eval_opimpl.
        This is a bug ugly, but too bad: record a mapping from op to w_opimpl.
        """
        self.opimpl[op] = w_opimpl
        return super().eval_opimpl(op, w_opimpl, args_wam)

    def shift_expr(self, expr: ast.Expr, wam: W_MetaArg) -> ast.Expr:
        """
        Shift an expression.

        "wam" is the result of "eval_expr(expr)".
        """
        if wam.color == "blue":
            return make_const(self.vm, expr.loc, wam.w_val)
        else:
            return magic_dispatch(self, "shift_expr", expr, wam)

    def shift_opimpl(
        self, op: ast.Node, w_opimpl: W_OpImpl, orig_args: list[ast.Expr]
    ) -> ast.Expr:
        if w_opimpl.is_const():
            assert w_opimpl.w_const is not None
            return make_const(self.vm, op.loc, w_opimpl.w_const)

        assert w_opimpl.is_func_call()
        func = make_const(self.vm, op.loc, w_opimpl.w_func)
        real_args = self._shift_opimpl_args(w_opimpl, orig_args)
        return ast.Call(op.loc, func, real_args)

    def _shift_opimpl_args(
        self, w_opimpl: W_OpImpl, orig_args: list[ast.Expr]
    ) -> list[ast.Expr]:
        def getarg(spec: ArgSpec) -> ast.Expr:
            if isinstance(spec, ArgSpec.Arg):
                return orig_args[spec.i]
            elif isinstance(spec, ArgSpec.Const):
                return make_const(self.vm, spec.loc, spec.w_const)
            elif isinstance(spec, ArgSpec.Convert):
                expT = getarg(spec.expT)
                gotT = getarg(spec.gotT)
                arg = getarg(spec.arg)
                return self.shift_opimpl(arg, spec.w_conv_opimpl, [expT, gotT, arg])
            else:
                assert False

        real_args = [getarg(spec) for spec in w_opimpl.args]
        return real_args

    def shift_expr_Constant(self, const: ast.Constant, wam: W_MetaArg) -> ast.Expr:
        return const

    def shift_expr_Name(self, name: ast.Name, wam: W_MetaArg) -> ast.Expr:
        return self.specialized_names[name]

    def shift_expr_NameLocal(self, name: ast.NameLocal, wam: W_MetaArg) -> ast.Expr:
        return name

    def shift_expr_NameOuterDirect(
        self, name: ast.NameOuterDirect, wam: W_MetaArg
    ) -> ast.Expr:
        return name

    def shift_expr_NameOuterCell(
        self, name: ast.NameOuterCell, wam: W_MetaArg
    ) -> ast.Expr:
        return name

    def shift_expr_BinOp(self, binop: ast.BinOp, wam: W_MetaArg) -> ast.Expr:
        w_opimpl = self.opimpl[binop]
        l = self.shifted_expr[binop.left]
        r = self.shifted_expr[binop.right]
        return self.shift_opimpl(binop, w_opimpl, [l, r])

    def shift_expr_CmpOp(self, op: ast.CmpOp, wam: W_MetaArg) -> ast.Expr:
        w_opimpl = self.opimpl[op]
        l = self.shifted_expr[op.left]
        r = self.shifted_expr[op.right]
        return self.shift_opimpl(op, w_opimpl, [l, r])

    def shift_expr_And(self, op: ast.And, wam: W_MetaArg) -> ast.Expr:
        l = self.shifted_expr[op.left]
        r = self.shifted_expr[op.right]
        return ast.And(op.loc, l, r)

    def shift_expr_Or(self, op: ast.Or, wam: W_MetaArg) -> ast.Expr:
        l = self.shifted_expr[op.left]
        r = self.shifted_expr[op.right]
        return ast.Or(op.loc, l, r)

    def shift_expr_UnaryOp(self, unop: ast.UnaryOp, wam: W_MetaArg) -> ast.Expr:
        w_opimpl = self.opimpl[unop]
        v = self.shifted_expr[unop.value]
        return self.shift_opimpl(unop, w_opimpl, [v])

    def shift_expr_List(self, lst: ast.List, wam: W_MetaArg) -> ast.Expr:
        # this logic is equivalent to what we have in eval_expr_List. Instead of
        # actually doing calls, we create an AST instead.
        if len(lst.items) == 0:
            assert wam.w_static_T is SPY.w_EmptyListType
            return make_const(self.vm, lst.loc, SPY.w_empty_list)

        w_T = wam.w_static_T
        fqn_new = w_T.fqn.join("__new__")
        fqn_push = w_T.fqn.join("_push")

        # instantiate an empty list
        newlst = ast.Call(
            loc=lst.loc,
            func=ast.FQNConst(loc=lst.loc, fqn=fqn_new),
            args=[],
        )

        # add a call to push() for each item
        for item in lst.items:
            shifted_item = self.shifted_expr[item]
            newlst = ast.Call(
                item.loc,
                func=ast.FQNConst(loc=item.loc, fqn=fqn_push),
                args=[newlst, shifted_item],
            )
        return newlst

    def shift_expr_GetItem(self, op: ast.GetItem, wam: W_MetaArg) -> ast.Expr:
        w_opimpl = self.opimpl[op]
        v = self.shifted_expr[op.value]
        args = [self.shifted_expr[arg] for arg in op.args]
        return self.shift_opimpl(op, w_opimpl, [v] + args)

    def shift_expr_GetAttr(self, op: ast.GetAttr, wam: W_MetaArg) -> ast.Expr:
        w_opimpl = self.opimpl[op]
        v = self.shifted_expr[op.value]
        v_attr = self.shifted_expr[op.attr]
        return self.shift_opimpl(op, w_opimpl, [v, v_attr])

    def shift_expr_Call(self, call: ast.Call, wam: W_MetaArg) -> ast.Expr:
        w_opimpl = self.opimpl[call]
        newfunc = self.shifted_expr[call.func]
        newargs = [self.shifted_expr[arg] for arg in call.args]
        newcall = self.shift_opimpl(call, w_opimpl, [newfunc] + newargs)
        return newcall

    def shift_expr_CallMethod(self, op: ast.CallMethod, wam: W_MetaArg) -> ast.Expr:
        w_opimpl = self.opimpl[op]
        v_obj = self.shifted_expr[op.target]
        v_meth = self.shifted_expr[op.method]
        newargs_v = [self.shifted_expr[arg] for arg in op.args]
        return self.shift_opimpl(op, w_opimpl, [v_obj, v_meth] + newargs_v)

    def shift_expr_AssignExpr(
        self, assignexpr: ast.AssignExpr, wam: W_MetaArg
    ) -> ast.Expr:
        specialized = self.specialized_assignexprs[assignexpr]
        new_value = self.shifted_expr[assignexpr.value]
        return specialized.replace(value=new_value)
