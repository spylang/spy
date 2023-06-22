import spy.ast
from spy.irgen.typechecker import TypeChecker
from spy.irgen.symtable import SymTable
from spy.vm.vm import SPyVM
from spy.vm.codeobject import W_CodeObject, OpCode
from spy.vm.function import W_FunctionType
from spy.util import magic_dispatch

class CodeGen:
    """
    Compile the body of spy.ast.FuncDef into a W_CodeObject
    """
    vm: SPyVM
    t: TypeChecker
    funcdef: spy.ast.FuncDef
    scope: SymTable
    w_code: W_CodeObject

    def __init__(self,
                 vm: SPyVM,
                 t: TypeChecker,
                 funcdef: spy.ast.FuncDef) -> None:
        self.vm = vm
        self.t = t
        self.funcdef = funcdef
        w_functype, scope = t.get_funcdef_info(funcdef)
        self.scope = scope
        self.w_code = W_CodeObject(self.funcdef.name, w_functype=w_functype)
        self.add_local_variables()

    def add_local_variables(self) -> None:
        for sym in self.scope.symbols.values():
            if sym.name == '@return':
                continue
            self.w_code.declare_local(sym.name, sym.w_type)

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

    def exec_stmt(self, stmt: spy.ast.Stmt) -> None:
        """
        Compile a statement.

        Pop all the operands from the stack, don't push any result.
        """
        magic_dispatch(self, 'do_exec', stmt)

    def eval_expr(self, expr: spy.ast.Expr) -> None:
        """
        Compile an expression.

        Pop all the operands from the stack, push the result on the stack.
        """
        magic_dispatch(self, 'do_eval', expr)

    # ====== statements ======

    def do_exec_Return(self, ret: spy.ast.Return) -> None:
        assert ret.value is not None
        self.eval_expr(ret.value)
        self.emit('return')

    def do_exec_VarDef(self, vardef: spy.ast.VarDef) -> None:
        # sanity check, the var must be in the local scope
        assert vardef.name in self.scope.symbols
        assert vardef.value is not None
        self.eval_expr(vardef.value)
        self.emit('local_set', vardef.name)

    # ====== expressions ======

    def do_eval_Constant(self, const: spy.ast.Constant) -> None:
        assert type(const.value) is int
        self.emit('const_load', self.vm.wrap(const.value))

    def do_eval_Name(self, expr: spy.ast.Name) -> None:
        varname = expr.id
        sym = self.scope.lookup(varname)
        assert sym is not None
        if sym.scope is self.scope:
            # local variable
            self.emit('local_get', varname)
        else:
            # outer variable, maybe global
            assert False, 'XXX todo'

    def do_eval_Add(self, binop: spy.ast.BinOp) -> None:
        w_i32 = self.vm.builtins.w_i32
        w_ltype = self.t.get_expr_type(binop.left)
        w_rtype = self.t.get_expr_type(binop.right)
        if w_ltype is w_i32 and w_rtype is w_i32:
            self.eval_expr(binop.left)
            self.eval_expr(binop.right)
            self.emit('i32_add')
        else:
            raise NotImplementedError(f'+ op between {w_ltype.name} and {w_rtype.name}')
