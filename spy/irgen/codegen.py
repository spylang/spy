from typing import NoReturn
from types import NoneType
import spy.ast
from spy.fqn import FQN
from spy.location import Loc
from spy.irgen.typechecker import TypeChecker
from spy.errors import SPyCompileError
from spy.vm.vm import SPyVM, Builtins as B
from spy.vm.object import W_Object
from spy.vm.codeobject import W_CodeObject, OpCode
from spy.vm.function import W_FuncType
from spy.util import magic_dispatch

class LocalVarsComputer:
    funcdef: spy.ast.FuncDef
    locals: set[str]

    def __init__(self, funcdef: spy.ast.FuncDef) -> None:
        self.funcdef = funcdef
        self.locals = set()

    def add(self, name: str) -> None:
        self.locals.add(name)

    def compute(self) -> set[str]:
        for arg in self.funcdef.args:
            self.add(arg.name)
        #
        # XXX this is horribly wrong, because it takes into consideration also
        # the stmts inside inner funcs
        for stmt in self.funcdef.walk(spy.ast.Stmt):
            if isinstance(stmt, spy.ast.Assign):
                import pdb;pdb.set_trace()

        for inner in self.funcdef.walk(spy.ast.FuncDef):
            assert isinstance(inner, spy.ast.FuncDef)
            if inner is self.funcdef:
                continue
            self.add(inner.name)
        #

        # hack hack hack, we need a proper ScopeAnalyzer
        for name in self.funcdef.walk(spy.ast.Name):
            if name.id in self.locals:
                name.scope = 'local'

        return self.locals

class CodeGen:
    """
    Compile the body of spy.ast.FuncDef into a W_CodeObject

    XXX this should be killed
    """
    vm: SPyVM
    funcdef: spy.ast.FuncDef
    w_code: W_CodeObject
    last_lineno: int

    def __init__(self,
                 vm: SPyVM,
                 funcdef: spy.ast.FuncDef
                 ) -> None:
        self.vm = vm
        self.funcdef = funcdef
        self.w_code = W_CodeObject.from_funcdef(funcdef)
        self.last_lineno = -1
        self.local_vars = LocalVarsComputer(funcdef).compute()

    def make_w_code(self) -> W_CodeObject:
        for stmt in self.funcdef.body:
            self.gen_stmt(stmt)
        loc = self.funcdef.loc.make_end_loc()
        self.emit(loc, 'load_const', B.w_None)
        self.emit(loc, 'return')
        return self.w_code

    def emit(self, loc: Loc, name: str, *args: object) -> OpCode:
        """
        Emit an OpCode into the w_code body.
        """
        assert isinstance(loc, Loc)
        if self.last_lineno != loc.line_start:
            # emit a 'line' opcode
            op = OpCode('line', loc, loc.line_start)
            self.w_code.body.append(op)
            self.last_lineno = loc.line_start
        #
        op = OpCode(name, loc, *args)
        self.w_code.body.append(op)
        return op

    def error(self, primary: str, secondary: str, loc: Loc) -> NoReturn:
        raise SPyCompileError.simple(primary, secondary, loc)

    def gen_stmt(self, stmt: spy.ast.Stmt) -> None:
        """
        Compile a statement.

        Pop all the operands from the stack, don't push any result.
        """
        magic_dispatch(self, 'gen_stmt', stmt)

    def gen_expr(self, expr: spy.ast.Expr) -> None:
        """
        Compile an expression.

        Pop all the operands from the stack, push the result on the stack.
        """
        magic_dispatch(self, 'gen_expr', expr)

    # ====== statements ======

    def gen_eval_FuncDef(self, funcdef: spy.ast.FuncDef) -> None:
        assert self.funcdef.color == 'blue', (
            'closures are allowed only in @blue functions'
        )
        argnames = []
        for arg in funcdef.args:
            argnames.append(arg.name)
            self.gen_expr(arg.type)
        self.gen_expr(funcdef.return_type)
        self.emit(funcdef.loc, 'make_func_type', tuple(argnames))
        self.emit(funcdef.loc, 'dup')
        self.emit(funcdef.loc, 'declare_local', funcdef.name)
        #
        LocalVarsComputer(funcdef).compute()
        self.emit(funcdef.loc, 'load_const', funcdef)
        self.emit(funcdef.loc, 'make_function_ast')

    def gen_stmt_FuncDef(self, funcdef: spy.ast.FuncDef) -> None:
        self.gen_eval_FuncDef(funcdef)
        self.emit(funcdef.loc, 'store_local', funcdef.name)

    def gen_stmt_Return(self, ret: spy.ast.Return) -> None:
        assert ret.value is not None
        self.gen_expr(ret.value)
        self.emit(ret.loc, 'return')

    # ====== expressions ======

    def gen_expr_Constant(self, const: spy.ast.Constant) -> None:
        # according to _ast.pyi, the type of const.value can be one of the
        # following:
        #     None, str, bytes, bool, int, float, complex, Ellipsis
        w_const = None
        T = type(const.value)
        if T in (int, bool, str, NoneType):
            w_const = self.vm.wrap(const.value)
        elif T in (bytes, float, complex, Ellipsis):
            self.error(f'unsupported literal: {const.value!r}',
                       f'this is not supported yet', const.loc)
        else:
            assert False, f'Unexpected literal: {const.value}'
        #
        self.emit(const.loc, 'load_const', w_const)

    def gen_expr_Name(self, expr: spy.ast.Name) -> None:
        varname = expr.id
        if varname in self.local_vars:
            self.emit(expr.loc, 'load_local', varname)
        else:
            self.emit(expr.loc, 'load_nonlocal', varname)
