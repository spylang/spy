from spy import ast
from spy.util import magic_dispatch
from spy.textbuilder import TextBuilder

class SPyBackend:
    """
    SPy backend: convert an AST back to SPy code.

    Mostly used for testing.
    """
    mod: ast.Module

    def __init__(self, mod: ast.Module) -> None:
        self.mod = mod
        self.out = TextBuilder(use_colors=False)
        self.w = self.out.w
        self.wl = self.out.wl

    def build(self) -> str:
        for decl in self.mod.decls:
            self.emit_decl(decl)
        return self.out.build()

    def emit_decl(self, decl: ast.Decl) -> None:
        magic_dispatch(self, 'emit_decl', decl)

    def emit_stmt(self, stmt: ast.Stmt) -> None:
        magic_dispatch(self, 'emit_stmt', stmt)

    def gen_expr(self, expr: ast.Expr) -> str:
        return magic_dispatch(self, 'gen_expr', expr)

    # declarations

    def emit_decl_GlobalFuncDef(self, decl: ast.GlobalFuncDef) -> None:
        self.emit_stmt(decl.funcdef)

    # statements

    def _format_arglist(self, args: list[ast.FuncArg]) -> str:
        l = []
        for arg in args:
            t = self.gen_expr(arg.type)
            l.append(f'{arg.name}: {t}')
        return ', '.join(l)

    def emit_stmt_FuncDef(self, funcdef: ast.FuncDef) -> None:
        args = self._format_arglist(funcdef.args)
        ret = self.gen_expr(funcdef.return_type)
        self.wl(f'def {funcdef.name}({args}) -> {ret}:')
        with self.out.indent():
            for stmt in funcdef.body:
                self.emit_stmt(stmt)

    def emit_stmt_Pass(self, stmt: ast.Pass) -> None:
        self.wl('pass')

    def emit_stmt_Return(self, ret: ast.Return) -> None:
        v = self.gen_expr(ret.value)
        self.wl(f'return {v}')

    def emit_stmt_Assign(self, assign: ast.Assign) -> None:
        v = self.gen_expr(assign.value)
        self.wl(f'{assign.target} = {v}')

    # expressions

    def gen_expr_Constant(self, const: ast.Constant) -> str:
        return repr(const.value)

    def gen_expr_Name(self, name: ast.Name) -> str:
        return name.id

    def gen_expr_BinOp(self, binop: ast.BinOp) -> str:
        l = self.gen_expr(binop.left)
        r = self.gen_expr(binop.right)
        if binop.left.precedence < binop.precedence:
            l = f'({l})'
        if binop.right.precedence < binop.precedence:
            r = f'({r})'
        return f'{l} {binop.op} {r}'

    gen_expr_Add = gen_expr_BinOp
    gen_expr_Sub = gen_expr_BinOp
    gen_expr_Mul = gen_expr_BinOp
    gen_expr_Div = gen_expr_BinOp
