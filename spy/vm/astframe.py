from typing import TYPE_CHECKING, Any, Optional, NoReturn, Sequence
from types import NoneType
from dataclasses import dataclass
from spy import ast
from spy.location import Loc
from spy.errors import (SPyRuntimeAbort, SPyTypeError, SPyNameError,
                        SPyRuntimeError, maybe_plural)
from spy.irgen.symtable import Symbol, Color
from spy.fqn import FQN
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type
from spy.vm.primitive import W_Bool
from spy.vm.function import W_Func, W_FuncType, W_ASTFunc, Namespace
from spy.vm.func_adapter import W_FuncAdapter
from spy.vm.list import W_List, W_ListType
from spy.vm.tuple import W_Tuple
from spy.vm.modules.unsafe.struct import W_StructType
from spy.vm.typechecker import TypeChecker, maybe_blue
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.modules.operator import OP, OP_from_token
from spy.vm.modules.operator.convop import CONVERT_maybe
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

    def __init__(self, vm: 'SPyVM', w_func: W_ASTFunc,
                 *,
                 color: Color
                 ) -> None:
        assert isinstance(w_func, W_ASTFunc)
        self.vm = vm
        self.w_func = w_func
        self.funcdef = w_func.funcdef
        self._locals = {}
        self.t = TypeChecker(vm, self.w_func)
        #
        # a "red" frame performs concrete computation
        # a "blue" frame performs abstract computation on red values, and
        # concrete computation on blue values
        self.color = color

    def __repr__(self) -> str:
        if self.w_func.redshifted:
            extra = ' (redshifted)'
        elif self.w_func.color == 'blue':
            extra = ' (blue)'
        else:
            extra = ''
        return f'<{self.color} ASTFrame for {self.w_func.fqn}{extra}>'

    @property
    def abstract_interpretation(self):
        return self.color == 'blue'

    @property
    def is_module_body(self) -> bool:
        return self.w_func.fqn.is_module()

    def get_unique_FQN_maybe(self, fqn: FQN) -> FQN:
        """
        Return an unique FQN to use for a type or function.

        If we are executing a module body, we can assume that the FQN is
        already unique and just return it, else we ask the VM to compute one.
        """
        if self.is_module_body:
            return fqn
        else:
            return self.vm.get_unique_FQN(fqn)

    def store_local(self, name: str, w_value: W_Object) -> None:
        self._locals[name] = w_value

    def load_local(self, name: str) -> W_Object:
        w_obj = self._locals.get(name)
        if w_obj is None:
            raise SPyRuntimeError('read from uninitialized local')
        return w_obj

    def run(self, args_w: Sequence[W_Object]) -> W_Object:
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

    def init_arguments(self, args_w: Sequence[W_Object]) -> None:
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

    # "newtyle" is a temporary param, I want to make sure that tests crash hard
    # in old calling locations
    def eval_expr(self, expr: ast.Expr, *, newstyle,
                  w_target_type: Optional[W_Type] = None
                  ) -> W_OpArg:
        self.t.check_expr(expr)
        w_typeconv = self.t.expr_conv.get(expr) # XXX kill this
        wop = magic_dispatch(self, 'eval_expr', expr)
        # apply the type converter, if present
        if w_target_type:
            assert w_typeconv is None
            w_typeconv = CONVERT_maybe(self.vm, w_target_type, wop)

        if self.w_func.redshifted:
            # this is just a sanity check. After redshifting, all type
            # conversions should be explicit. If w_typeconv is not None here,
            # it means that Doppler failed to insert the appropriate
            # conversion
            assert w_typeconv is None

        if w_typeconv is None:
            return wop
        else:
            if self.abstract_interpretation:
                w_val = None
            else:
                w_val = self.vm.fast_call(w_typeconv, [wop.w_val])
            return W_OpArg(
                wop.color,
                w_typeconv.w_functype.w_restype,
                wop.loc,
                sym=wop.sym,
                w_val=w_val
            )

    def eval_expr_type(self, expr: ast.Expr) -> W_Type:
        wop = self.eval_expr(expr, newstyle=True)
        w_val = wop.w_val
        if isinstance(w_val, W_Type):
            self.vm.make_fqn_const(w_val)
            return w_val
        w_valtype = self.vm.dynamic_type(w_val)
        msg = f'expected `type`, got `{w_valtype.fqn.human_name}`'
        raise SPyTypeError.simple(msg, "expected `type`", expr.loc)

    # ==== statements ====

    def exec_stmt_Pass(self, stmt: ast.Pass) -> None:
        pass

    def exec_stmt_Return(self, ret: ast.Return) -> None:
        wop = self.eval_expr(ret.value, newstyle=True)
        raise Return(wop.w_val)

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
        fqn = self.w_func.fqn.join(funcdef.name)
        fqn = self.get_unique_FQN_maybe(fqn)
        # XXX we should capture only the names actually used in the inner func
        closure = self.w_func.closure + (self._locals,)
        w_func = W_ASTFunc(w_functype, fqn, funcdef, closure)
        self.store_local(funcdef.name, w_func)
        self.vm.add_global(fqn, w_func)

    def exec_stmt_ClassDef(self, classdef: ast.ClassDef) -> None:
        d = {}
        for vardef in classdef.fields:
            assert vardef.kind == 'var'
            d[vardef.name] = self.eval_expr_type(vardef.type)
        #
        assert classdef.is_struct, 'only structs are supported for now'
        fqn = self.w_func.fqn.join(classdef.name)
        fqn = self.get_unique_FQN_maybe(fqn)
        w_struct_type = W_StructType(fqn, d)
        w_meta_type = self.vm.dynamic_type(w_struct_type)
        self.t.lazy_check_ClassDef(classdef, w_meta_type)
        self.store_local(classdef.name, w_struct_type)
        self.vm.add_global(fqn, w_struct_type)

    def exec_stmt_VarDef(self, vardef: ast.VarDef) -> None:
        w_type = self.eval_expr_type(vardef.type)
        self.t.lazy_check_VarDef(vardef, w_type)

    def exec_stmt_Assign(self, assign: ast.Assign) -> None:
        wop = self.eval_expr(assign.value, newstyle=True)
        self._exec_assign(assign.target.value, wop.w_val)

    def exec_stmt_UnpackAssign(self, unpack: ast.UnpackAssign) -> None:
        w_tup = self.eval_expr(unpack.value)
        assert isinstance(w_tup, W_Tuple)
        exp = len(unpack.targets)
        got = len(w_tup.items_w)
        if exp != got:
            raise SPyRuntimeError(
                f"Wrong number of values to unpack: expected {exp}, got {got}"
            )
        for target, w_val in zip(unpack.targets, w_tup.items_w):
            self._exec_assign(target.value, w_val)

    def _exec_assign(self, target: str, w_val: W_Object) -> None:
        # XXX this is semi-wrong. We need to add an AST field to keep track of
        # which scope we want to assign to. For now we just assume that if
        # it's not local, it's module.
        sym = self.funcdef.symtable.lookup(target)
        if sym.is_local:
            self.store_local(target, w_val)
        elif sym.fqn is not None:
            assert sym.color == 'red'
            self.vm.store_global(sym.fqn, w_val)
        else:
            assert False, 'closures not implemented yet'


    def exec_stmt_SetAttr(self, node: ast.SetAttr) -> None:
        w_attr = self.vm.wrap(node.attr.value) # XXX maybe just eval op.attr?
        wop_target = self.eval_expr(node.target, newstyle=True)
        wop_attr = W_OpArg('blue', B.w_str, node.loc, w_val=w_attr)
        wop_value = self.eval_expr(node.value, newstyle=True)
        w_opimpl = self.vm.call_OP(
            OP.w_SETATTR,
            [wop_target, wop_attr, wop_value]
        )
        self.call_opimpl(w_opimpl, [wop_target, wop_attr, wop_value], node.loc)

    def exec_stmt_SetItem(self, node: ast.SetItem) -> None:
        w_opimpl = self.t.opimpl[node]
        w_target = self.eval_expr(node.target)
        w_index = self.eval_expr(node.index)
        w_value = self.eval_expr(node.value)
        self.vm.fast_call(w_opimpl, [w_target, w_index, w_value])

    def exec_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> None:
        self.eval_expr(stmt.value, newstyle=True)

    def exec_stmt_If(self, if_node: ast.If) -> None:
        wop_cond = self.eval_expr(if_node.test, newstyle=True,
                                  w_target_type=B.w_bool)
        assert isinstance(wop_cond.w_val, W_Bool)
        if self.vm.is_True(wop_cond.w_val):
            for stmt in if_node.then_body:
                self.exec_stmt(stmt)
        else:
            for stmt in if_node.else_body:
                self.exec_stmt(stmt)

    def exec_stmt_While(self, while_node: ast.While) -> None:
        while True:
            wop_cond = self.eval_expr(while_node.test, newstyle=True)
            assert isinstance(wop_cond.w_val, W_Bool)
            if self.vm.is_False(wop_cond.w_val):
                break
            for stmt in while_node.body:
                self.exec_stmt(stmt)

    # ==== expressions ====

    def eval_expr_Constant(self, const: ast.Constant) -> W_OpArg:
        # unsupported literals are rejected directly by the parser, see
        # Parser.from_py_expr_Constant
        T = type(const.value)
        assert T in (int, float, bool, NoneType)
        color, w_type = self.t.check_expr_Constant(const)
        w_val = self.vm.wrap(const.value)
        return W_OpArg(color, w_type, const.loc, w_val=w_val)

    def eval_expr_StrConst(self, const: ast.StrConst) -> W_OpArg:
        color, w_type = self.t.check_expr_StrConst(const)
        w_val = self.vm.wrap(const.value)
        return W_OpArg(color, w_type, const.loc, w_val=w_val)

    def eval_expr_FQNConst(self, const: ast.FQNConst) -> W_OpArg:
        w_value = self.vm.lookup_global(const.fqn)
        assert w_value is not None
        return W_OpArg.from_w_obj(self.vm, w_value)

    def eval_expr_Name(self, name: ast.Name) -> W_OpArg:
        color, w_type = self.t.check_expr_Name(name)
        sym = self.w_func.funcdef.symtable.lookup(name.id)
        if color == 'red' and self.abstract_interpretation:
            # this is a red variable and we are doing abstract interpretation,
            # so we don't/can't put a specific value.
            w_val = None
        elif sym.fqn is not None:
            w_val = self.vm.lookup_global(sym.fqn)
            assert w_val is not None, \
                f'{sym.fqn} not found. Bug in the ScopeAnalyzer?'
        elif sym.is_local:
            w_val = self.load_local(name.id)
        else:
            namespace = self.w_func.closure[sym.level]
            w_val = namespace[sym.name]
            assert w_val is not None
        return W_OpArg(color, w_type, name.loc, sym=sym, w_val=w_val)

    def call_opimpl(self, w_opimpl: W_Func, args_wop: list[W_OpArg],
                    loc: Loc) -> W_OpArg:
        # hack hack hack
        # result color:
        #   - pure function and blue arguments -> blue
        #   - red function -> red
        #   - blue function -> blue
        # XXX what happens if we try to call a blue func with red arguments?
        w_functype = w_opimpl.w_functype
        if w_opimpl.is_pure():
            colors = [wop.color for wop in args_wop]
            color = maybe_blue(*colors)
        else:
            color = w_functype.color

        if color == 'red' and self.abstract_interpretation:
            w_res = None
        else:
            args_w = [wop.w_val for wop in args_wop]
            w_res = self.vm.fast_call(w_opimpl, args_w)

        return W_OpArg(
            color,
            w_functype.w_restype,
            loc,
            w_val=w_res)

    def eval_expr_BinOp(self, binop: ast.BinOp) -> W_OpArg:
        w_OP = OP_from_token(binop.op) # e.g., w_ADD, w_MUL, etc.
        wop_l = self.eval_expr(binop.left, newstyle=True)
        wop_r = self.eval_expr(binop.right, newstyle=True)
        w_opimpl = self.vm.call_OP(w_OP, [wop_l, wop_r])
        return self.call_opimpl(w_opimpl, [wop_l, wop_r], binop.loc)

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

    def eval_expr_Call(self, call: ast.Call) -> W_OpArg:
        wop_func = self.eval_expr(call.func, newstyle=True)
        # STATIC_TYPE is special, because it doesn't evaluate its arguments
        if wop_func.w_val is B.w_STATIC_TYPE:
            return self._eval_STATIC_TYPE(call)
        args_wop = [self.eval_expr(arg, newstyle=True) for arg in call.args]
        w_opimpl = self.vm.call_OP(OP.w_CALL, [wop_func]+args_wop)
        return self.call_opimpl(w_opimpl, [wop_func]+args_wop, call.loc)

    def _eval_STATIC_TYPE(self, call: ast.Call) -> W_OpArg:
        assert len(call.args) == 1
        arg = call.args[0]
        if isinstance(arg, ast.Name):
            wop = self.eval_expr(arg, newstyle=True)
            w_argtype = wop.w_static_type
            return W_OpArg.from_w_obj(self.vm, w_argtype)
        msg = 'STATIC_TYPE works only on simple expressions'
        OP = arg.__class__.__name__
        raise SPyTypeError.simple(msg, f'{OP} not allowed here', arg.loc)

    def eval_expr_CallMethod(self, op: ast.CallMethod) -> W_Object:
        w_opimpl = self.t.opimpl[op]
        w_target = self.eval_expr(op.target)
        w_method = self.eval_expr(op.method)
        args_w = [self.eval_expr(arg) for arg in op.args]
        return self.vm.fast_call(w_opimpl, [w_target, w_method] + args_w)

    def eval_expr_GetItem(self, op: ast.GetItem) -> W_OpArg:
        wop_obj = self.eval_expr(op.value, newstyle=True)
        wop_i = self.eval_expr(op.index, newstyle=True)
        w_opimpl = self.vm.call_OP(OP.w_GETITEM, [wop_obj, wop_i])
        return self.call_opimpl(w_opimpl, [wop_obj, wop_i], op.loc)

    def eval_expr_GetAttr(self, op: ast.GetAttr) -> W_OpArg:
        w_attr = self.vm.wrap(op.attr.value) # XXX maybe just eval op.attr?
        wop_obj = self.eval_expr(op.value, newstyle=True)
        wop_attr = W_OpArg('blue', B.w_str, op.loc, w_val=w_attr)
        w_opimpl = self.vm.call_OP(OP.w_GETATTR, [wop_obj, wop_attr])
        return self.call_opimpl(w_opimpl, [wop_obj, wop_attr], op.loc)

    def eval_expr_List(self, op: ast.List) -> W_Object:
        color, w_listtype = self.t.check_expr(op)
        assert isinstance(w_listtype, W_ListType)
        items_w = [self.eval_expr(item) for item in op.items]
        return W_List(w_listtype, items_w)

    def eval_expr_Tuple(self, op: ast.Tuple) -> W_Object:
        color, w_tupletype = self.t.check_expr(op)
        assert w_tupletype is B.w_tuple
        items_w = [self.eval_expr(item) for item in op.items]
        return W_Tuple(items_w)
