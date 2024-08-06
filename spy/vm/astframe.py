from typing import TYPE_CHECKING, Any, Optional, NoReturn
from types import NoneType
from dataclasses import dataclass
from spy import ast
from spy.fqn import FQN, QN
from spy.location import Loc
from spy.errors import (SPyRuntimeAbort, SPyTypeError, SPyNameError,
                        SPyRuntimeError, maybe_plural)
from spy.irgen.symtable import Symbol, Color
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type
from spy.vm.function import W_Func, W_FuncType, W_ASTFunc, Namespace
from spy.vm.list import W_List
from spy.vm.tuple import W_Tuple
from spy.vm.typechecker import TypeChecker
from spy.vm.typeconverter import TypeConverter
from spy.util import magic_dispatch
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

class Return(Exception):
    w_value: W_Object

    def __init__(self, w_value: W_Object) -> None:
        self.w_value = w_value


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
        return f'<ASTFrame for {self.w_func.qn}>'

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
            if self.w_func.w_functype.w_restype in (B.w_void, B.w_dynamic):
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

    def eval_expr(self, expr: ast.Expr) -> W_Object:
        self.t.check_expr(expr)
        typeconv = self.t.expr_conv.get(expr)
        w_val = magic_dispatch(self, 'eval_expr', expr)
        if typeconv is None:
            return w_val
        else:
            # apply the type converter, if present
            return typeconv.convert(self.vm, w_val)

    def eval_expr_type(self, expr: ast.Expr) -> W_Type:
        w_val = self.eval_expr(expr)
        if isinstance(w_val, W_Type):
            return w_val
        w_valtype = self.vm.dynamic_type(w_val)
        msg = f'expected `type`, got `{w_valtype.name}`'
        raise SPyTypeError.simple(msg, "expected `type`", expr.loc)

    # ==== statements ====

    def exec_stmt_Return(self, ret: ast.Return) -> None:
        w_val = self.eval_expr(ret.value)
        raise Return(w_val)

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
        modname = self.w_func.qn.modname # the module of the "outer" function
        qn = QN(modname=modname, attr=funcdef.name)
        # XXX we should capture only the names actually used in the inner func
        closure = self.w_func.closure + (self._locals,)
        w_func = W_ASTFunc(w_functype, qn, funcdef, closure)
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
        w_val = self.eval_expr(assign.value)
        if sym.is_local:
            self.store_local(name, w_val)
        elif sym.fqn is not None:
            assert sym.color == 'red'
            self.vm.store_global(sym.fqn, w_val)
        else:
            assert False, 'closures not implemented yet'

    def exec_stmt_SetAttr(self, node: ast.SetAttr) -> None:
        w_opimpl = self.t.opimpl[node]
        w_target = self.eval_expr(node.target)
        w_attr = self.vm.wrap(node.attr)
        w_value = self.eval_expr(node.value)
        self.vm.call_function(w_opimpl, [w_target, w_attr, w_value])

    def exec_stmt_SetItem(self, node: ast.SetItem) -> None:
        w_opimpl = self.t.opimpl[node]
        w_target = self.eval_expr(node.target)
        w_index = self.eval_expr(node.index)
        w_value = self.eval_expr(node.value)
        self.vm.call_function(w_opimpl, [w_target, w_index, w_value])

    def exec_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> None:
        self.eval_expr(stmt.value)

    def exec_stmt_If(self, if_node: ast.If) -> None:
        w_cond = self.eval_expr(if_node.test)
        if self.vm.is_True(w_cond):
            for stmt in if_node.then_body:
                self.exec_stmt(stmt)
        else:
            for stmt in if_node.else_body:
                self.exec_stmt(stmt)

    def exec_stmt_While(self, while_node: ast.While) -> None:
        while True:
            w_cond = self.eval_expr(while_node.test)
            if self.vm.is_False(w_cond):
                break
            for stmt in while_node.body:
                self.exec_stmt(stmt)

    # ==== expressions ====

    def eval_expr_Constant(self, const: ast.Constant) -> W_Object:
        # unsupported literals are rejected directly by the parser, see
        # Parser.from_py_expr_Constant
        T = type(const.value)
        assert T in (int, float, bool, str, NoneType)
        return self.vm.wrap(const.value)

    def eval_expr_FQNConst(self, const: ast.FQNConst) -> W_Object:
        w_value = self.vm.lookup_global(const.fqn)
        assert w_value is not None
        return w_value

    def eval_expr_Name(self, name: ast.Name) -> W_Object:
        sym = self.w_func.funcdef.symtable.lookup(name.id)
        if sym.fqn is not None:
            w_value = self.vm.lookup_global(sym.fqn)
            assert w_value is not None, \
                f'{sym.fqn} not found. Bug in the ScopeAnalyzer?'
            return w_value
        elif sym.is_local:
            return self.load_local(name.id)
        else:
            namespace = self.w_func.closure[sym.level]
            w_value = namespace[sym.name]
            assert w_value is not None
            return w_value

    def eval_expr_BinOp(self, binop: ast.BinOp) -> W_Object:
        w_opimpl = self.t.opimpl[binop]
        assert w_opimpl, 'bug in the typechecker'
        w_l = self.eval_expr(binop.left)
        w_r = self.eval_expr(binop.right)
        w_res = self.vm.call_function(w_opimpl, [w_l, w_r])
        return w_res

    eval_expr_Add = eval_expr_BinOp
    eval_expr_Sub = eval_expr_BinOp
    eval_expr_Mul = eval_expr_BinOp
    eval_expr_Div = eval_expr_BinOp
    eval_expr_Eq = eval_expr_BinOp
    eval_expr_NotEq = eval_expr_BinOp
    eval_expr_Lt = eval_expr_BinOp
    eval_expr_LtE = eval_expr_BinOp
    eval_expr_Gt = eval_expr_BinOp
    eval_expr_GtE = eval_expr_BinOp

    def eval_expr_Call(self, call: ast.Call) -> W_Object:
        color, w_functype = self.t.check_expr(call.func)
        if call in self.t.opimpl:
            return self._eval_call_opimpl(call, color, w_functype)
        else:
            return self._eval_call_func(call, color, w_functype)

    def _eval_call_opimpl(self, call: ast.Call, color: Color,
                          w_functype: W_Type) -> W_Object:
        w_opimpl = self.t.opimpl[call]
        w_target = self.eval_expr(call.func)
        args_w = [self.eval_expr(arg) for arg in call.args]
        w_res = self.vm.call_function(w_opimpl, [w_target] + args_w)
        return w_res

    def _eval_call_func(self, call: ast.Call, color: Color,
                        w_functype: W_Type) -> W_Object:
        assert color == 'blue', 'indirect calls not supported'
        w_func = self.eval_expr(call.func)

        if w_functype is B.w_dynamic:
            # if the static type is `dynamic` and thing is not a function,
            # it's a TypeError
            if not isinstance(w_func, W_Func):
                t = self.vm.dynamic_type(w_func)
                raise SPyTypeError(f'cannot call objects of type `{t.name}`')
        else:
            # if the static type is not `dynamic` and the thing is not a
            # function, it's a bug in the typechecker
            assert isinstance(w_func, W_Func)

        if w_func is B.w_STATIC_TYPE:
            return self._eval_STATIC_TYPE(call)
        else:
            args_w = [self.eval_expr(arg) for arg in call.args]
            w_res = self.vm.call_function(w_func, args_w)
            return w_res

    def _eval_STATIC_TYPE(self, call: ast.Call) -> W_Object:
        assert len(call.args) == 1
        arg = call.args[0]
        if isinstance(arg, ast.Name):
            _, w_argtype = self.t.check_expr(arg)
            return w_argtype
        msg = 'STATIC_TYPE works only on simple expressions'
        OP = arg.__class__.__name__
        raise SPyTypeError.simple(msg, f'{OP} not allowed here', arg.loc)

    def eval_expr_CallMethod(self, op: ast.CallMethod) -> W_Object:
        w_opimpl = self.t.opimpl[op]
        w_target = self.eval_expr(op.target)
        w_method = self.vm.wrap(op.method)
        arg_w = [self.eval_expr(arg) for arg in op.args]
        w_res = self.vm.call_function(w_opimpl, [w_target, w_method] + arg_w)
        return w_res

    def eval_expr_GetItem(self, op: ast.GetItem) -> W_Object:
        w_opimpl = self.t.opimpl[op]
        w_val = self.eval_expr(op.value)
        w_i = self.eval_expr(op.index)
        w_res = self.vm.call_function(w_opimpl, [w_val, w_i])
        return w_res

    def eval_expr_GetAttr(self, op: ast.GetAttr) -> W_Object:
        # this is suboptimal, but good enough for now: ideally, we would like
        # to support two cases:
        #
        #   1. "generic" impls, which are called with [w_val, w_attr]
        #   2. "specialized" impls, which are called with only [w_val]
        w_opimpl = self.t.opimpl[op]
        w_val = self.eval_expr(op.value)
        w_attr = self.vm.wrap(op.attr)
        w_res = self.vm.call_function(w_opimpl, [w_val, w_attr])
        return w_res

    def eval_expr_List(self, op: ast.List) -> W_Object:
        color, w_listtype = self.t.check_expr(op)
        items_w = [self.eval_expr(item) for item in op.items]
        assert issubclass(w_listtype.pyclass, W_List)
        return w_listtype.pyclass(items_w) # type: ignore

    def eval_expr_Tuple(self, op: ast.Tuple) -> W_Object:
        color, w_tupletype = self.t.check_expr(op)
        assert w_tupletype is B.w_tuple
        items_w = [self.eval_expr(item) for item in op.items]
        return W_Tuple(items_w)
