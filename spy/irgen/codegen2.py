import spy.ast
from spy.fqn import FQN
from spy.location import Loc
from spy.irgen.typechecker import TypeChecker
from spy.vm.vm import SPyVM, Builtins as B
from spy.vm.object import W_Object
from spy.vm.codeobject import W_CodeObject, OpCode
from spy.vm.function import W_FuncType
from spy.util import magic_dispatch

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
                 funcdef: spy.ast.FuncDef) -> None:
        self.vm = vm
        self.t = t
        self.funcdef = funcdef
        w_functype = t.funcdef_types[funcdef]
        # XXX fix me:
        #   - FQN should not be attached to code objects
        #   - w_functype should not belong to code objects
        self.w_code = W_CodeObject(
            FQN(modname='xxx', attr=funcdef.name),
            w_functype=w_functype,
            filename=self.funcdef.loc.filename,
            lineno=self.funcdef.loc.line_start)
        self.last_lineno = -1

    def make_w_code(self) -> W_CodeObject:
        for stmt in self.funcdef.body:
            self.gen_stmt(stmt)
        #
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
        op = OpCode(name, *args)
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

    def gen_stmt_Return(self, ret: spy.ast.Return) -> None:
        assert ret.value is not None
        self.gen_expr(ret.value)
        self.emit(ret.loc, 'return')

    # ====== expressions ======

    def gen_expr_Constant(self, const: spy.ast.Constant) -> None:
        w_const = self.t.get_w_const(const)
        self.emit(const.loc, 'load_const', w_const)

    def gen_expr_Name(self, expr: spy.ast.Name) -> None:
        # XXX we assume that it's a local but it's wrong
        varname = expr.id
        self.w_code.declare_local('x', B.w_object) # XXX
        self.emit(expr.loc, 'load_local', varname)
