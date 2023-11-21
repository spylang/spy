import spy.ast
from spy.fqn import FQN
from spy.location import Loc
from spy.irgen.typechecker import TypeChecker
from spy.vm.vm import SPyVM, Builtins as B
from spy.vm.object import W_Object
from spy.vm.codeobject import W_CodeObject, OpCode
from spy.vm.function import W_FuncType
from spy.util import magic_dispatch

class LocalVarsComputer:

    def __init__(self, funcdef):
        self.funcdef = funcdef
        self.locals = set()

    def add(self, name):
        self.locals.add(name)

    def compute(self):
        for arg in self.funcdef.args:
            self.add(arg.name)
        #
        # XXX this is horribly wrong, because it takes into consideration also
        # the stmts inside inner funcs
        for stmt in self.funcdef.walk(spy.ast.Stmt):
            if isinstance(stmt, spy.ast.Assign):
                import pdb;pdb.set_trace()

        for inner in self.funcdef.walk(spy.ast.FuncDef):
            if inner is self.funcdef:
                continue
            self.add(inner.name)
        #
        return self.locals

class CodeGen:
    """
    Compile the body of spy.ast.FuncDef into a W_CodeObject
    """
    vm: SPyVM
    t: TypeChecker # XXX we use it only for get_w_const
    funcdef: spy.ast.FuncDef
    w_code: W_CodeObject
    last_lineno: int

    def __init__(self,
                 vm: SPyVM,
                 t: TypeChecker,
                 funcdef: spy.ast.FuncDef
                 ) -> None:
        self.vm = vm
        self.t = t
        self.funcdef = funcdef
        self.w_code = W_CodeObject(
            funcdef.name,
            filename=self.funcdef.loc.filename,
            lineno=self.funcdef.loc.line_start)
        self.last_lineno = -1
        self.local_vars = LocalVarsComputer(funcdef).compute()

    def make_w_code(self) -> W_CodeObject:
        # prologue: declare args and pops them from stack
        rtype = self.funcdef.return_type
        self.gen_expr(rtype)
        self.emit(rtype.loc, 'declare_local', '@return')
        #
        for arg in self.funcdef.args:
            self.gen_expr(arg.type)
            self.emit(arg.loc, 'declare_local', arg.name)
            self.emit(arg.loc, 'store_local', arg.name)
        self.w_code.mark_end_prologue()
        #
        # main body
        for stmt in self.funcdef.body:
            self.gen_stmt(stmt)
        #
        # epilogue
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
            op = OpCode('line', loc.line_start)
            self.w_code.body.append(op)
            self.last_lineno = loc.line_start
        #
        op = OpCode(name, *args, loc=loc)
        self.w_code.body.append(op)
        return op

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
        inner_codegen = CodeGen(self.vm, self.t, funcdef)
        w_code = inner_codegen.make_w_code()

        argnames = []
        for arg in funcdef.args:
            argnames.append(arg.name)
            self.gen_expr(arg.type)
        self.gen_expr(funcdef.return_type)
        self.emit(funcdef.loc, 'make_func_type', tuple(argnames))
        self.emit(funcdef.loc, 'dup')
        self.emit(funcdef.loc, 'declare_local', funcdef.name)
        #
        self.emit(funcdef.loc, 'load_const', w_code)
        self.emit(funcdef.loc, 'make_function')

    def gen_stmt_FuncDef(self, funcdef: spy.ast.FuncDef) -> None:
        self.gen_eval_FuncDef(funcdef)
        self.emit(funcdef.loc, 'store_local', funcdef.name)

    def gen_stmt_Return(self, ret: spy.ast.Return) -> None:
        assert ret.value is not None
        self.gen_expr(ret.value)
        self.emit(ret.loc, 'return')

    # ====== expressions ======

    def gen_expr_Constant(self, const: spy.ast.Constant) -> None:
        w_const = self.t.get_w_const(const)
        self.emit(const.loc, 'load_const', w_const)

    def gen_expr_Name(self, expr: spy.ast.Name) -> None:
        varname = expr.id
        if varname in self.local_vars:
            self.emit(expr.loc, 'load_local', varname)
        else:
            self.emit(expr.loc, 'load_nonlocal', varname)
