from typing import TYPE_CHECKING, Any
from types import NoneType
from spy import ast
from spy.fqn import FQN
from spy.location import Loc
from spy.errors import SPyRuntimeAbort, SPyTypeError, SPyNameError
from spy.vm.object import W_Object, W_Type, W_i32, W_bool
from spy.vm.str import W_str
from spy.vm.codeobject import W_CodeObject, OpCode
from spy.vm.varstorage import VarStorage
from spy.vm.function import W_Func, W_UserFunc, W_FuncType, W_ASTFunc
from spy.vm import helpers
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
    locals: VarStorage

    def __init__(self, vm: 'SPyVM', w_func: W_ASTFunc) -> None:
        assert isinstance(w_func, W_ASTFunc)
        self.vm = vm
        self.w_func = w_func
        self.funcdef = w_func.funcdef
        self.locals = VarStorage(vm, f"'{self.funcdef.name} locals'")

    def __repr__(self) -> str:
        return f'<ASTFrame for {self.w_func.fqn}>'

    def run(self, args_w: list[W_Object]) -> W_Object:
        self.init_arguments(args_w)
        try:
            for stmt in self.funcdef.body:
                self.exec_stmt(stmt)
            assert False, 'no return?'
        except Return as e:
            return e.w_value

    def init_arguments(self, args_w: list[W_Object]) -> None:
        """
        - declare the local vars for the arguments and @return
        - store the arguments in args_w in the appropriate local var
        """
        w_functype = self.w_func.w_functype
        # XXX do we need it?
        self.locals.declare(self.funcdef.return_type.loc,
                            '@return', w_functype.w_restype)
        #
        params = self.w_func.w_functype.params
        arglocs = [arg.loc for arg in self.funcdef.args]
        for loc, param, w_arg in zip(arglocs, params, args_w, strict=True):
            self.locals.declare(loc, param.name, param.w_type)
            self.locals.set(loc, param.name, w_arg)

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
        self.locals.typecheck(stmt.loc, '@return', w_value)
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
        w_func = W_ASTFunc(fqn, w_functype, funcdef)
        #
        # store it in the locals
        self.locals.declare(funcdef.loc, funcdef.name, w_func.w_functype)
        self.locals.set(funcdef.loc, funcdef.name, w_func)

    def exec_stmt_VarDef(self, vardef: ast.VarDef) -> None:
        assert vardef.name in self.funcdef.locals, 'bug in the ScopeAnalyzer?'
        w_type = self.eval_expr(vardef.type)
        w_value = self.eval_expr(vardef.value)
        self.locals.declare(vardef.type.loc, vardef.name, w_type)
        self.locals.set(vardef.value.loc, vardef.name, w_value)

    # ==== expressions ====

    def eval_expr_Constant(self, const: ast.Constant) -> W_Object:
        # unsupported literals are rejected directly by the parser, see
        # Parser.from_py_expr_Constant
        T = type(const.value)
        assert T in (int, bool, str, NoneType)
        return self.vm.wrap(const.value)

    def eval_expr_Name(self, name: ast.Name) -> W_Object:
        if name.scope == 'local':
            return self.locals.get(name.id)
        elif name.scope == 'outer':
            # XXX for now we assume it's a builtin
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

    def eval_expr_Add(self, op: ast.Add) -> W_Object:
        from spy.vm.vm import Builtins as B
        # XXX we should use the static types
        w_l = self.eval_expr(op.left)
        w_r = self.eval_expr(op.right)
        w_ltype = self.vm.dynamic_type(w_l)
        w_rtype = self.vm.dynamic_type(w_r)
        if w_ltype is B.w_i32 and w_rtype is B.w_i32:
            l = self.vm.unwrap(w_l)
            r = self.vm.unwrap(w_r)
            return self.vm.wrap(l + r)
        #
        assert False, 'WIP'
