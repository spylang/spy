from typing import TYPE_CHECKING, Any, Optional
from types import NoneType
from dataclasses import dataclass
from spy import ast
from spy.fqn import FQN
from spy.location import Loc
from spy.errors import (SPyRuntimeAbort, SPyTypeError, SPyNameError,
                        SPyRuntimeError)
from spy.vm.builtins import B
from spy.vm.object import W_Object, W_Type, W_i32, W_bool
from spy.vm.str import W_str
from spy.vm.codeobject import W_CodeObject, OpCode
from spy.vm.function import W_Func, W_UserFunc, W_FuncType, W_ASTFunc
from spy.vm import helpers
from spy.vm.typechecker import TypeChecker
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
    w_val: W_Object


class ASTFrame:
    vm: 'SPyVM'
    w_func: W_ASTFunc
    funcdef: ast.FuncDef
    locals: dict[str, Optional[W_Object]]

    def __init__(self, vm: 'SPyVM', w_func: W_ASTFunc) -> None:
        assert isinstance(w_func, W_ASTFunc)
        self.vm = vm
        self.w_func = w_func
        self.funcdef = w_func.funcdef
        self.locals = {}
        self.t = TypeChecker(vm)

    def __repr__(self) -> str:
        return f'<ASTFrame for {self.w_func.fqn}>'

    def declare_local(self, loc: Loc, name: str, w_type: W_Type) -> None:
        assert name not in self.locals, f'variable already declared: {name}'
        self.t.declare_local(loc, name, w_type)
        self.locals[name] = None

    def store_local(self, loc: Loc, name: str, w_val: W_Object) -> None:
        self.t.typecheck_local(loc, name, w_val)
        self.locals[name] = w_val

    def load_local(self, name: str) -> FrameVal:
        assert name in self.locals
        w_obj = self.locals[name]
        if w_obj is None:
            raise SPyRuntimeError('read from uninitialized local')
        w_type = self.t.locals_types_w[name] # XXX
        return FrameVal(w_type, w_obj)

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
        - declare the local vars for the arguments and @return
        - store the arguments in args_w in the appropriate local var
        """
        w_functype = self.w_func.w_functype
        # XXX do we need it?
        self.declare_local(self.funcdef.return_type.loc,
                           '@return', w_functype.w_restype)
        #
        params = self.w_func.w_functype.params
        arglocs = [arg.loc for arg in self.funcdef.args]
        for loc, param, w_arg in zip(arglocs, params, args_w, strict=True):
            self.declare_local(loc, param.name, param.w_type)
            self.store_local(loc, param.name, w_arg)

    def exec_stmt(self, stmt: ast.Stmt) -> None:
        return magic_dispatch(self, 'exec_stmt', stmt)

    def eval_expr(self, expr: ast.Expr) -> FrameVal:
        return magic_dispatch(self, 'eval_expr', expr)

    def eval_expr_object(self, expr: ast.Expr) -> W_Object:
        fv = self.eval_expr(expr)
        return fv.w_val

    def eval_expr_type(self, expr: ast.Expr) -> W_Type:
        fv = self.eval_expr(expr)
        if isinstance(fv.w_val, W_Type):
            return fv.w_val
        w_valtype = self.vm.dynamic_type(fv.w_val)
        msg = f'expected `type`, got `{w_valtype.name}`'
        raise SPyTypeError.simple(msg, "expected `type`", expr.loc)

    # ==== statements ====

    def exec_stmt_Return(self, stmt: ast.Return) -> None:
        fv = self.eval_expr(stmt.value)
        self.t.typecheck_local(stmt.loc, '@return', fv.w_val)
        raise Return(fv.w_val)

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
        #
        # create the w_func
        fqn = FQN(modname='???', attr=funcdef.name)
        w_func = W_ASTFunc(fqn, self.w_func.modname, w_functype, funcdef)
        #
        # store it in the locals
        self.declare_local(funcdef.loc, funcdef.name, w_func.w_functype)
        self.store_local(funcdef.loc, funcdef.name, w_func)

    def exec_stmt_VarDef(self, vardef: ast.VarDef) -> None:
        assert vardef.name in self.funcdef.locals, 'bug in the ScopeAnalyzer?'
        assert vardef.value is not None, 'WIP?'
        w_type = self.eval_expr_type(vardef.type)
        self.declare_local(vardef.type.loc, vardef.name, w_type)
        w_value = self.eval_expr_object(vardef.value)
        self.store_local(vardef.value.loc, vardef.name, w_value)

    def exec_stmt_Assign(self, assign: ast.Assign) -> None:
        # XXX this looks wrong. We need to add an AST field to keep track of
        # which scope we want to assign to. For now we just assume that if
        # it's not local, it's module.
        name = assign.target
        w_value = self.eval_expr_object(assign.value)
        if name in self.funcdef.locals:
            # NOTE: we are consciously forgetting the STATIC type here. In the
            # interpreter, what we care about is that the dynamic type is
            # correct. It is the job of the doppler transformer to insert a
            # downcast if necessary.
            if name not in self.locals:
                # first assignment, implicit declaration
                w_type = self.vm.dynamic_type(w_value)
                self.declare_local(assign.loc, name, w_type)
            self.store_local(assign.value.loc, assign.target, w_value)
        else:
            # we assume it's module-level.
            # XXX we should check that this global is red/non-constant
            fqn = FQN(modname=self.w_func.modname, attr=name)
            self.vm.store_global(fqn, w_value)

    # ==== expressions ====

    def eval_expr_Constant(self, const: ast.Constant) -> FrameVal:
        # unsupported literals are rejected directly by the parser, see
        # Parser.from_py_expr_Constant
        T = type(const.value)
        assert T in (int, bool, str, NoneType)
        w_val = self.vm.wrap(const.value)
        w_type = self.vm.dynamic_type(w_val)
        return FrameVal(w_type, w_val)

    def eval_expr_Name(self, name: ast.Name) -> FrameVal:
        if name.scope == 'local':
            return self.load_local(name.id)
        elif name.scope in ('module', 'builtins'):
            if name.scope == 'builtins':
                fqn = FQN(modname='builtins', attr=name.id)
            else:
                fqn = FQN(modname=self.w_func.modname, attr=name.id)
            w_value = self.vm.lookup_global(fqn)
            assert w_value is not None
            # XXX this is wrong: we should keep track of the static type of
            # FQNs :(
            w_type = self.vm.dynamic_type(w_value)
            return FrameVal(w_type, w_value)
        elif name.scope == 'non-declared':
            msg = f"name `{name.id}` is not defined"
            raise SPyNameError.simple(msg, "not found in this scope", name.loc)
        elif name.scope == "unknown":
            assert False, "bug in the ScopeAnalyzer?"
        else:
            assert False, f"Invalid value for scope: {name.scope}"

    def eval_expr_BinOp(self, binop: ast.BinOp) -> FrameVal:
        from spy.vm.builtins import B
        fv_l = self.eval_expr(binop.left)
        fv_r = self.eval_expr(binop.right)
        # NOTE: we do the dispatch based on the STATIC types of the operands,
        # not the dynamic ones.
        w_ltype = fv_l.w_static_type
        w_rtype = fv_r.w_static_type
        if w_ltype is B.w_i32 and w_rtype is B.w_i32:
            l = self.vm.unwrap(fv_l.w_val)
            r = self.vm.unwrap(fv_r.w_val)
            if binop.op == '+':
                return FrameVal(B.w_i32, self.vm.wrap(l + r))
            elif binop.op == '*':
                return FrameVal(B.w_i32, self.vm.wrap(l * r))
        #
        lt = w_ltype.name
        rt = w_rtype.name
        err = SPyTypeError(f'cannot do `{lt}` {binop.op} `{rt}`')
        err.add('error', f'this is `{lt}`', binop.left.loc)
        err.add('error', f'this is `{rt}`', binop.right.loc)
        raise err

    eval_expr_Add = eval_expr_BinOp
    eval_expr_Mul = eval_expr_BinOp
