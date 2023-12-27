from typing import Literal
from spy import ast
from spy.fqn import FQN
from spy.vm.vm import SPyVM
from spy.vm.object import W_Object
from spy.vm.function import W_ASTFunc, FuncParam
from spy.util import magic_dispatch
from spy.textbuilder import TextBuilder

FQN_FORMAT = Literal['full', 'short', 'no']

class SPyBackend:
    """
    SPy backend: convert an AST back to SPy code.

    Mostly used for testing.
    """

    def __init__(self, vm: SPyVM, *, fqn_format: FQN_FORMAT = 'short') -> None:
        self.vm = vm
        self.fqn_format = fqn_format
        self.out = TextBuilder(use_colors=False)
        self.w = self.out.w
        self.wl = self.out.wl

    def dump_funcdef(self, funcdef: ast.FuncDef) -> str:
        self.emit_stmt(funcdef)
        return self.out.build()

    def dump_w_func(self, w_func: W_ASTFunc) -> str:
        w_functype = w_func.w_functype
        name = w_func.fqn.attr
        params = self.fmt_params(w_functype.params)
        ret = self.fmt_w_obj(w_functype.w_restype)
        self.wl(f'def {name}({params}) -> {ret}:')
        with self.out.indent():
            for stmt in w_func.funcdef.body:
                self.emit_stmt(stmt)
        return self.out.build()

    def fmt_params(self, params: list[FuncParam]) -> str:
        l = []
        for p in params:
            t = self.fmt_w_obj(p.w_type)
            l.append(f'{p.name}: {t}')
        return ', '.join(l)

    def fmt_w_obj(self, w_obj: W_Object) -> str:
        # this assumes that w_obj has a valid FQN
        fqn = self.vm.reverse_lookup_global(w_obj)
        assert fqn is not None
        return self.fmt_fqn(fqn)

    def fmt_fqn(self, fqn: FQN) -> str:
        if self.fqn_format == 'no':
            return fqn.attr # don't show the namespace
        elif self.fqn_format == 'short' and fqn.modname == 'builtins':
            return fqn.attr # don't show builtins::
        else:
            return f'`{fqn}`'

    # ==============

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

    def emit_stmt_Pass(self, stmt: ast.Pass) -> None:
        self.wl('pass')

    def emit_stmt_Return(self, ret: ast.Return) -> None:
        v = self.gen_expr(ret.value)
        self.wl(f'return {v}')

    def emit_stmt_Assign(self, assign: ast.Assign) -> None:
        v = self.gen_expr(assign.value)
        self.wl(f'{assign.target} = {v}')

    def emit_stmt_VarDef(self, vardef: ast.VarDef) -> None:
        assert vardef.value is not None, 'XXX'
        t = self.gen_expr(vardef.type)
        v = self.gen_expr(vardef.value)
        self.wl(f'{vardef.name}: {t} = {v}')

    # expressions

    def gen_expr_Constant(self, const: ast.Constant) -> str:
        return repr(const.value)

    def gen_expr_FQNConst(self, const: ast.FQNConst) -> str:
        return self.fmt_fqn(const.fqn)

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
