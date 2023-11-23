from typing import TYPE_CHECKING, Any
from types import NoneType
from spy import ast
from spy.fqn import FQN
from spy.location import Loc
from spy.errors import SPyRuntimeAbort, SPyTypeError
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
    def __init__(self, w_value):
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
            self.locals.set(param.name, w_arg)

    def exec_stmt(self, stmt: ast.Stmt) -> None:
        return magic_dispatch(self, 'exec_stmt', stmt)

    def eval_expr(self, expr: ast.Expr) -> W_Object:
        return magic_dispatch(self, 'eval_expr', expr)

    # ==== statements ====

    def exec_stmt_Return(self, stmt: ast.Return) -> None:
        w_value = self.eval_expr(stmt.value)
        # XXX typecheck?
        raise Return(w_value)

    # ==== expressions ====

    def eval_expr_Constant(self, const: ast.Constant) -> W_Object:
        # according to _ast.pyi, the type of const.value can be one of the
        # following:
        #     None, str, bytes, bool, int, float, complex, Ellipsis
        T = type(const.value)
        if T in (int, bool, str, NoneType):
            return self.vm.wrap(const.value)
        elif T in (bytes, float, complex, Ellipsis):
            self.error(f'unsupported literal: {const.value!r}',
                       f'this is not supported yet', const.loc)
        else:
            assert False, f'Unexpected literal: {const.value}'

    def eval_expr_Name(self, name: ast.Name) -> W_Object:
        # XXX typecheck?
        if name.scope == 'local':
            return self.locals.get(name.id)
        else:
            # XXX for now we assume it's a builtin
            fqn = FQN(modname='builtins', attr=name.id)
            w_value = self.vm.lookup_global(fqn)
            assert w_value is not None
            return w_value
