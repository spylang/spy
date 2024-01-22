from typing import TYPE_CHECKING, Any, Optional, NoReturn
from types import NoneType
from dataclasses import dataclass
from spy import ast
from spy.fqn import FQN
from spy.location import Loc
from spy.errors import (SPyRuntimeAbort, SPyTypeError, SPyNameError,
                        SPyRuntimeError, maybe_plural)
from spy.irgen.symtable import Symbol
from spy.vm.builtins import B
from spy.vm.object import W_Object, W_Type, W_i32, W_bool
from spy.vm.str import W_str
from spy.vm.function import W_Func, W_FuncType, W_ASTFunc, Namespace
from spy.vm import ops
from spy.vm.typechecker import TypeChecker
from spy.vm.typeconverter import TypeConverter
from spy.util import magic_dispatch
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

class Return(Exception):
    w_value: W_Object

    def __init__(self, w_value: W_Object) -> None:
        self.w_value = w_value



@dataclass
class FrameVal:
    """
    Small wrapper around W_Object which also keeps track of its static type.
    The naming convention is to call them fv_*.
    """
    w_static_type: W_Type
    w_value: W_Object

    @property
    def w_bool_value(self) -> W_bool:
        assert isinstance(self.w_value, W_bool)
        return self.w_value

class ASTFrame:
    vm: 'SPyVM'
    w_func: W_ASTFunc
    funcdef: ast.FuncDef
    _locals: Namespace
    t: TypeChecker

    def __init__(self, vm: 'SPyVM', w_func: W_ASTFunc) -> None:
        assert isinstance(w_func, W_ASTFunc)
        self.vm = vm
        self.w_func = w_func
        self.funcdef = w_func.funcdef
        self._locals = {}
        self.t = TypeChecker(vm, self.w_func)

    def __repr__(self) -> str:
        return f'<ASTFrame for {self.w_func.fqn}>'

    def store_local(self, name: str, w_value: W_Object) -> None:
        self._locals[name] = w_value

    def load_local(self, name: str) -> W_Object:
        w_obj = self._locals.get(name)
        if w_obj is None:
            raise SPyRuntimeError('read from uninitialized local')
        return w_obj

    def run(self, args_w: list[W_Object]) -> W_Object:
        self.init_arguments(args_w)
        try:
            for stmt in self.funcdef.body:
                self.exec_stmt(stmt)
            #
            # we reached the end of the function. If it's void, we can return
            # None, else it's an error.
            if self.w_func.w_functype.w_restype is B.w_void:
                return B.w_None
            else:
                loc = self.w_func.funcdef.loc.make_end_loc()
                msg = 'reached the end of the function without a `return`'
                raise SPyTypeError.simple(msg, 'no return', loc)

        except Return as e:
            return e.w_value

    def init_arguments(self, args_w: list[W_Object]) -> None:
        """
        Store the arguments in args_w in the appropriate local var
        """
        w_functype = self.w_func.w_functype
        params = self.w_func.w_functype.params
        arglocs = [arg.loc for arg in self.funcdef.args]
        for loc, param, w_arg in zip(arglocs, params, args_w, strict=True):
            # we assume that the arguments' types are correct. It's not the
            # job of astframe to raise SPyTypeError if there is a type
            # mismatch here, it is the job of vm.call_function
            assert self.vm.isinstance(w_arg, param.w_type)
            self.store_local(param.name, w_arg)

    def exec_stmt(self, stmt: ast.Stmt) -> None:
        self.t.check_stmt(stmt)
        return magic_dispatch(self, 'exec_stmt', stmt)

    def eval_expr(self, expr: ast.Expr) -> FrameVal:
        self.t.check_expr(expr)
        typeconv = self.t.expr_conv.get(expr)
        fv = magic_dispatch(self, 'eval_expr', expr)
        if typeconv is None:
            return fv
        else:
            # apply the type converter, if present. Note that the static type
            # of the expression is the one given by the converter, not the
            # original one in fv.w_static_type
            w_newvalue = typeconv.convert(self.vm, fv.w_value)
            return FrameVal(typeconv.w_type, w_newvalue)

    def eval_expr_object(self, expr: ast.Expr) -> W_Object:
        fv = self.eval_expr(expr)
        return fv.w_value

    def eval_expr_type(self, expr: ast.Expr) -> W_Type:
        fv = self.eval_expr(expr)
        if isinstance(fv.w_value, W_Type):
            assert fv.w_static_type is B.w_type
            return fv.w_value
        w_valtype = self.vm.dynamic_type(fv.w_value)
        msg = f'expected `type`, got `{w_valtype.name}`'
        raise SPyTypeError.simple(msg, "expected `type`", expr.loc)

    # ==== statements ====

    def exec_stmt_Return(self, ret: ast.Return) -> None:
        fv = self.eval_expr(ret.value)
        raise Return(fv.w_value)

    def exec_stmt_FuncDef(self, funcdef: ast.FuncDef) -> None:
        # evaluate the functype
        d = {}
        for arg in funcdef.args:
            d[arg.name] = self.eval_expr_type(arg.type)
        w_restype = self.eval_expr_type(funcdef.return_type)
        w_functype = W_FuncType.make(
            color = funcdef.color,
            w_restype = w_restype,
            **d)
        self.t.lazy_check_FuncDef(funcdef, w_functype)
        #
        # create the w_func
        fqn = FQN(modname='???', attr=funcdef.name)
        # XXX we should capture only the names actually used in the inner func
        closure = self.w_func.closure + (self._locals,)
        w_func = W_ASTFunc(w_functype, fqn, funcdef, closure)
        self.store_local(funcdef.name, w_func)

    def exec_stmt_VarDef(self, vardef: ast.VarDef) -> None:
        w_type = self.eval_expr_type(vardef.type)
        self.t.lazy_check_VarDef(vardef, w_type)

    def exec_stmt_Assign(self, assign: ast.Assign) -> None:
        # XXX this is semi-wrong. We need to add an AST field to keep track of
        # which scope we want to assign to. For now we just assume that if
        # it's not local, it's module.
        name = assign.target
        sym = self.funcdef.symtable.lookup(name)
        fv = self.eval_expr(assign.value)
        if sym.is_local:
            self.store_local(name, fv.w_value)
        elif sym.fqn is not None:
            assert sym.color == 'red'
            self.vm.store_global(sym.fqn, fv.w_value)
        else:
            assert False, 'closures not implemented yet'

    def exec_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> None:
        self.eval_expr(stmt.value)

    def exec_stmt_If(self, if_node: ast.If) -> None:
        fv = self.eval_expr(if_node.test)
        if self.vm.is_True(fv.w_bool_value):
            for stmt in if_node.then_body:
                self.exec_stmt(stmt)
        else:
            for stmt in if_node.else_body:
                self.exec_stmt(stmt)

    def exec_stmt_While(self, while_node: ast.While) -> None:
        while True:
            fv = self.eval_expr(while_node.test)
            if self.vm.is_False(fv.w_bool_value):
                break
            for stmt in while_node.body:
                self.exec_stmt(stmt)

    # ==== expressions ====

    def eval_expr_Constant(self, const: ast.Constant) -> FrameVal:
        # unsupported literals are rejected directly by the parser, see
        # Parser.from_py_expr_Constant
        T = type(const.value)
        assert T in (int, bool, str, NoneType)
        color, w_type = self.t.check_expr_Constant(const)
        w_value = self.vm.wrap(const.value)
        return FrameVal(w_type, w_value)

    def eval_expr_FQNConst(self, const: ast.FQNConst) -> FrameVal:
        color, w_type = self.t.check_expr_FQNConst(const)
        w_value = self.vm.lookup_global(const.fqn)
        assert w_value is not None
        return FrameVal(w_type, w_value)

    def eval_expr_Name(self, name: ast.Name) -> FrameVal:
        color, w_type = self.t.check_expr_Name(name)
        sym = self.w_func.funcdef.symtable.lookup(name.id)
        if sym.fqn is not None:
            w_value = self.vm.lookup_global(sym.fqn)
            assert w_value is not None, \
                f'{sym.fqn} not found. Bug in the ScopeAnalyzer?'
            return FrameVal(w_type, w_value)
        elif sym.is_local:
            w_value = self.load_local(name.id)
            return FrameVal(w_type, w_value)
        else:
            namespace = self.w_func.closure[sym.level]
            w_value = namespace[sym.name]
            assert w_value is not None
            return FrameVal(w_type, w_value)

    def eval_expr_BinOp(self, binop: ast.BinOp) -> FrameVal:
        color, w_restype = self.t.check_expr_BinOp(binop)
        opimpl = self.t.expr_opimpl[binop]
        assert opimpl, 'bug in the typechecker'
        fv_l = self.eval_expr(binop.left)
        fv_r = self.eval_expr(binop.right)
        w_res = opimpl(self.vm, fv_l.w_value, fv_r.w_value)
        return FrameVal(w_restype, w_res)

    eval_expr_Add = eval_expr_BinOp
    eval_expr_Mul = eval_expr_BinOp

    def eval_expr_CompareOp(self, op: ast.CompareOp) -> FrameVal:
        self.t.check_expr_CompareOp(op)
        fv_l = self.eval_expr(op.left)
        fv_r = self.eval_expr(op.right)
        w_ltype = fv_l.w_static_type
        w_rtype = fv_r.w_static_type
        if w_ltype is B.w_i32 and w_rtype is B.w_i32:
            l = self.vm.unwrap(fv_l.w_value)
            r = self.vm.unwrap(fv_r.w_value)
            if   op.op == '==': res = (l == r)
            elif op.op == '!=': res = (l != r)
            elif op.op == '<':  res = (l <  r)
            elif op.op == '<=': res = (l <= r)
            elif op.op == '>':  res = (l >  r)
            elif op.op == '>=': res = (l >= r)
            return FrameVal(B.w_bool, self.vm.wrap(res))
        #
        assert False, 'Unsupported cmpop, bug in the typechecker'

    eval_expr_Eq = eval_expr_CompareOp
    eval_expr_NotEq = eval_expr_CompareOp
    eval_expr_Lt = eval_expr_CompareOp
    eval_expr_LtE = eval_expr_CompareOp
    eval_expr_Gt = eval_expr_CompareOp
    eval_expr_GtE = eval_expr_CompareOp

    def eval_expr_Call(self, call: ast.Call) -> FrameVal:
        color, w_restype = self.t.check_expr_Call(call)
        if isinstance(call.func, ast.HelperFunc):
            # special case CallHelper:
            args_w = [self.eval_expr_object(arg) for arg in call.args]
            return self.call_helper(call.func.funcname, args_w, w_restype)
        #
        fv_func = self.eval_expr(call.func)
        w_func = fv_func.w_value
        assert isinstance(w_func, W_Func)
        args_w = [self.eval_expr_object(arg) for arg in call.args]
        w_res = self.vm.call_function(w_func, args_w)
        return FrameVal(w_restype, w_res)

    def eval_expr_HelperFunc(self, node: ast.HelperFunc) -> FrameVal:
        # we should special-case a call to HelperFunc in eval_expr_Call
        assert False, 'should not be called'

    def call_helper(self, funcname: str, args_w: list[W_Object],
                    w_restype: W_Type) -> FrameVal:
        opimpl = ops.get(funcname)
        w_res = opimpl(self.vm, *args_w)
        return FrameVal(w_restype, w_res)

    def eval_expr_GetItem(self, op: ast.GetItem) -> FrameVal:
        color, w_restype = self.t.check_expr_GetItem(op)
        opimpl = self.t.expr_opimpl[op]
        fv_val = self.eval_expr(op.value)
        fv_index = self.eval_expr(op.index)
        w_res = opimpl(self.vm, fv_val.w_value, fv_index.w_value)
        return FrameVal(w_restype, w_res)
