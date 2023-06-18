import ast as py_ast
import spy.ast
from spy.vm.vm import SPyVM
from spy.vm.codeobject import W_CodeObject, OpCode


class CodeGen:
    """
    Compile the body of spy.ast.FuncDef into a W_CodeObject
    """
    vm: SPyVM
    funcdef: spy.ast.FuncDef
    w_code: W_CodeObject

    def __init__(self, vm: SPyVM, funcdef: spy.ast.FuncDef) -> None:
        self.vm = vm
        self.funcdef = funcdef
        self.w_code = W_CodeObject(self.funcdef.name)

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
        methname = f'do_exec_{stmt.__class__.__name__}'
        meth = getattr(self, methname, None)
        if meth is None:
            raise NotImplementedError(methname)
        meth(stmt)

    def eval_expr(self, expr: py_ast.expr) -> None:
        """
        Compile an expression.

        Pop all the operands from the stack, push the result on the stack.
        """
        methname = f'do_eval_{expr.__class__.__name__}'
        meth = getattr(self, methname, None)
        if meth is None:
            raise NotImplementedError(methname)
        meth(expr)

    def do_exec_Return(self, ret: py_ast.Return) -> None:
        assert ret.value is not None
        self.eval_expr(ret.value)
        self.emit('return')

    def do_eval_Constant(self, const: py_ast.Constant) -> None:
        # XXX we need a typechecking phase
        assert type(const.value) is int
        self.emit('i32_const', self.vm.wrap(const.value))
