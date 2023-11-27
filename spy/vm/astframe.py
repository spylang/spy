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
from spy.util import magic_dispatch
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

class Return(Exception):
    w_value: W_Object

    def __init__(self, w_value: W_Object) -> None:
        self.w_value = w_value

@dataclass
class LocalVar:
    loc: Loc                   # location of the declaration
    w_type: W_Type             # static type of the variable
    w_val: Optional[W_Object]  # None means "uninitialized"


class ASTFrame:
    vm: 'SPyVM'
    w_func: W_ASTFunc
    funcdef: ast.FuncDef
    locals: dict[str, LocalVar]

    def __init__(self, vm: 'SPyVM', w_func: W_ASTFunc) -> None:
        assert isinstance(w_func, W_ASTFunc)
        self.vm = vm
        self.w_func = w_func
        self.funcdef = w_func.funcdef
        self.locals = {}

    def __repr__(self) -> str:
        return f'<ASTFrame for {self.w_func.fqn}>'

    def declare_local(self, loc: Loc, name: str, w_type: W_Type) -> None:
        assert name not in self.locals, f'variable already declared: {name}'
        self.locals[name] = LocalVar(loc, w_type, None)

    def store_local(self, loc: Loc, name: str, w_val: W_Object) -> None:
        self.typecheck_local(loc, name, w_val)
        v = self.locals[name]
        v.w_val = w_val

    def load_local(self, name: str) -> W_Object:
        assert name in self.locals
        v = self.locals[name]
        if v.w_val is None:
            raise SPyRuntimeError('read from uninitialized local')
        return v.w_val

    def typecheck_local(self, got_loc: Loc, name: str, w_got: W_Object) -> None:
        assert name in self.locals
        v = self.locals[name]
        if self.vm.is_compatible_type(w_got, v.w_type):
            return
        err = SPyTypeError('mismatched types')
        got = self.vm.dynamic_type(w_got).name
        exp = v.w_type.name
        exp_loc = v.loc
        err.add('error', f'expected `{exp}`, got `{got}`', loc=got_loc)
        if name == '@return':
            because = 'because of return type'
        else:
            because = 'because of type declaration'
        err.add('note', f'expected `{exp}` {because}', loc=exp_loc)
        raise err

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

    def eval_expr(self, expr: ast.Expr) -> W_Object:
        return magic_dispatch(self, 'eval_expr', expr)

    def eval_expr_type(self, expr: ast.Expr) -> W_Type:
        w_val = self.eval_expr(expr)
        if isinstance(w_val, W_Type):
            return w_val
        w_valtype = self.vm.dynamic_type(w_val)
        msg = f'expected `type`, got `{w_valtype.name}`'
        raise SPyTypeError.simple(msg, "expected `type`", expr.loc)

    # ==== statements ====

    def exec_stmt_Return(self, stmt: ast.Return) -> None:
        w_value = self.eval_expr(stmt.value)
        self.typecheck_local(stmt.loc, '@return', w_value)
        raise Return(w_value)

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
        w_value = self.eval_expr(vardef.value)
        self.declare_local(vardef.type.loc, vardef.name, w_type)
        self.store_local(vardef.value.loc, vardef.name, w_value)

    def exec_stmt_Assign(self, assign: ast.Assign) -> None:
        # XXX this looks wrong. We need to add an AST field to keep track of
        # which scope we want to assign to. For now we just assume that if
        # it's not local, it's module.
        name = assign.target
        w_value = self.eval_expr(assign.value)
        if name in self.funcdef.locals:
            if name not in self.locals:
                # first assignment, implicit declaration
                w_type = self.vm.dynamic_type(w_value) # XXX static type?
                self.declare_local(assign.loc, name, w_type)
            self.store_local(assign.value.loc, assign.target, w_value)
        else:
            # we assume it's module-level.
            # XXX we should check that this global is red/non-constant
            fqn = FQN(modname=self.w_func.modname, attr=name)
            self.vm.store_global(fqn, w_value)

    # ==== expressions ====

    def eval_expr_Constant(self, const: ast.Constant) -> W_Object:
        # unsupported literals are rejected directly by the parser, see
        # Parser.from_py_expr_Constant
        T = type(const.value)
        assert T in (int, bool, str, NoneType)
        return self.vm.wrap(const.value)

    def eval_expr_Name(self, name: ast.Name) -> W_Object:
        if name.scope == 'local':
            return self.load_local(name.id)
        elif name.scope == 'module':
            fqn = FQN(modname=self.w_func.modname, attr=name.id)
            w_value = self.vm.lookup_global(fqn)
            assert w_value is not None
            return w_value
        elif name.scope == 'builtins':
            fqn = FQN(modname='builtins', attr=name.id)
            w_value = self.vm.lookup_global(fqn)
            assert w_value is not None
            return w_value
        elif name.scope == 'non-declared':
            msg = f"name `{name.id}` is not defined"
            raise SPyNameError.simple(msg, "not found in this scope", name.loc)
        elif name.scope == "unknown":
            assert False, "bug in the ScopeAnalyzer?"
        else:
            assert False, f"Invalid value for scope: {name.scope}"

    def eval_expr_BinOp(self, binop: ast.BinOp) -> W_Object:
        from spy.vm.builtins import B
        # XXX we should use the static types
        w_l = self.eval_expr(binop.left)
        w_r = self.eval_expr(binop.right)
        w_ltype = self.vm.dynamic_type(w_l)
        w_rtype = self.vm.dynamic_type(w_r)
        if w_ltype is B.w_i32 and w_rtype is B.w_i32:
            l = self.vm.unwrap(w_l)
            r = self.vm.unwrap(w_r)
            if binop.op == '+':
                return self.vm.wrap(l + r)
            elif binop.op == '*':
                return self.vm.wrap(l * r)
        #
        l = w_ltype.name
        r = w_rtype.name
        err = SPyTypeError(f'cannot do `{l}` {binop.op} `{r}`')
        err.add('error', f'this is `{l}`', binop.left.loc)
        err.add('error', f'this is `{r}`', binop.right.loc)
        raise err

    eval_expr_Add = eval_expr_BinOp
    eval_expr_Mul = eval_expr_BinOp
