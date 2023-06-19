import ast as py_ast
import spy.ast
from spy.vm.vm import SPyVM
from spy.vm.codeobject import W_CodeObject, OpCode
from spy.vm.function import W_FunctionType
from spy.util import magic_dispatch

class CodeGen:
    """
    Compile the body of spy.ast.FuncDef into a W_CodeObject
    """
    vm: SPyVM
    funcdef: spy.ast.FuncDef
    w_code: W_CodeObject

    def __init__(self, vm: SPyVM, funcdef: spy.ast.FuncDef,
                 w_functype: W_FunctionType) -> None:
        self.vm = vm
        self.funcdef = funcdef
        self.w_code = W_CodeObject(self.funcdef.name,
                                   w_restype=w_functype.w_restype)

    def make_w_code(self) -> W_CodeObject:
        for stmt in self.funcdef.body:
            self.exec_stmt(stmt)
        return self.w_code

    def emit(self, name: str, *args: object) -> None:
        """
        Emit an OpCode into the w_code body
        """
        opcode = OpCode(name, *args)
        self.w_code.body.append(opcode)

    def exec_stmt(self, stmt: py_ast.stmt) -> None:
        """
        Compile a statement.

        Pop all the operands from the stack, don't push any result.
        """
        magic_dispatch(self, 'do_exec', stmt)

    def eval_expr(self, expr: py_ast.expr) -> None:
        """
        Compile an expression.

        Pop all the operands from the stack, push the result on the stack.
        """
        magic_dispatch(self, 'do_eval', expr)

    def do_exec_Return(self, ret: py_ast.Return) -> None:
        assert ret.value is not None
        self.eval_expr(ret.value)
        self.emit('return')

    def do_eval_Constant(self, const: py_ast.Constant) -> None:
        # XXX we need a typechecking phase
        assert type(const.value) is int
        self.emit('const_load', self.vm.wrap(const.value))
