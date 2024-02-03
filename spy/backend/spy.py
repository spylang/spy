from typing import Literal, Optional
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

    def dump_mod(self, modname: str) -> str:
        w_mod = self.vm.modules_w[modname]
        for fqn, w_obj in w_mod.items_w():
            if isinstance(w_obj, W_ASTFunc) and w_obj.color == 'red':
                self.dump_w_func(w_obj)
                self.out.wl()
        return self.out.build()

    def dump_w_func(self, w_func: W_ASTFunc) -> str:
        fqn = w_func.fqn
        if fqn.uniq_suffix == '':
            # this is a global function, we can just use its name
            name = fqn.attr
        else:
            name = self.fmt_fqn(fqn)
        w_functype = w_func.w_functype
        params = self.fmt_params(w_functype.params)
        ret = self.fmt_w_obj(w_functype.w_restype)
        self.wl(f'def {name}({params}) -> {ret}:')
        with self.out.indent():
            for stmt in w_func.funcdef.body:
                self.emit_stmt(stmt)

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

    def fmt_expr(self, expr: ast.Expr) -> str:
        return magic_dispatch(self, 'fmt_expr', expr)

    # declarations

    def emit_decl_GlobalFuncDef(self, decl: ast.GlobalFuncDef) -> None:
        self.emit_stmt(decl.funcdef)

    # statements

    def emit_stmt_FuncDef(self, funcdef: ast.FuncDef) -> None:
        name = funcdef.name
        paramlist = []
        for funcarg in funcdef.args:
            n = funcarg.name
            t = self.fmt_expr(funcarg.type)
            paramlist.append(f'{n}: {t}')
        params = ', '.join(paramlist)
        ret = self.fmt_expr(funcdef.return_type)
        self.wl(f'def {name}({params}) -> {ret}:')
        with self.out.indent():
            for stmt in funcdef.body:
                self.emit_stmt(stmt)

    def emit_stmt_Pass(self, stmt: ast.Pass) -> None:
        self.wl('pass')

    def emit_stmt_Return(self, ret: ast.Return) -> None:
        v = self.fmt_expr(ret.value)
        self.wl(f'return {v}')

    def emit_stmt_Assign(self, assign: ast.Assign) -> None:
        v = self.fmt_expr(assign.value)
        self.wl(f'{assign.target} = {v}')

    def emit_stmt_VarDef(self, vardef: ast.VarDef) -> None:
        t = self.fmt_expr(vardef.type)
        self.wl(f'{vardef.name}: {t}')

    def emit_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> None:
        v = self.fmt_expr(stmt.value)
        self.wl(f'{v}')

    def emit_stmt_While(self, while_node: ast.While) -> None:
        test = self.fmt_expr(while_node.test)
        self.wl(f'while {test}:')
        with self.out.indent():
            for stmt in while_node.body:
                self.emit_stmt(stmt)

    # expressions

    def fmt_expr_Constant(self, const: ast.Constant) -> str:
        return repr(const.value)

    def fmt_expr_FQNConst(self, const: ast.FQNConst) -> str:
        return self.fmt_fqn(const.fqn)

    def fmt_expr_Name(self, name: ast.Name) -> str:
        return name.id

    def fmt_expr_BinOp(self, binop: ast.BinOp) -> str:
        l = self.fmt_expr(binop.left)
        r = self.fmt_expr(binop.right)
        if binop.left.precedence < binop.precedence:
            l = f'({l})'
        if binop.right.precedence < binop.precedence:
            r = f'({r})'
        return f'{l} {binop.op} {r}'

    fmt_expr_Add = fmt_expr_BinOp
    fmt_expr_Sub = fmt_expr_BinOp
    fmt_expr_Mul = fmt_expr_BinOp
    fmt_expr_Div = fmt_expr_BinOp


    # special cases
    FQN2BinOp = {
        FQN('operator::i32_add'): ast.Add,
        FQN('operator::i32_sub'): ast.Sub,
        FQN('operator::i32_mul'): ast.Mul,
        FQN('operator::i32_div'): ast.Div,
        FQN('operator::i32_eq'): ast.Eq,
        FQN('operator::i32_ne'): ast.NotEq,
        FQN('operator::i32_lt'): ast.Lt,
        FQN('operator::i32_le'): ast.LtE,
        FQN('operator::i32_gt'): ast.Gt,
        FQN('operator::i32_ge'): ast.GtE,
        #
        FQN('operator::f64_add'): ast.Add,
        FQN('operator::f64_sub'): ast.Sub,
        FQN('operator::f64_mul'): ast.Mul,
        FQN('operator::f64_div'): ast.Div,
        FQN('operator::f64_eq'): ast.Eq,
        FQN('operator::f64_ne'): ast.NotEq,
        FQN('operator::f64_lt'): ast.Lt,
        FQN('operator::f64_le'): ast.LtE,
        FQN('operator::f64_gt'): ast.Gt,
        FQN('operator::f64_ge'): ast.GtE,
    }

    def get_binop_maybe(self, func: ast.Expr) -> Optional[type[ast.BinOp]]:
        """
        Some opimpl are special-cased and turned back into a BinOp
        """
        if isinstance(func, ast.FQNConst):
            return self.FQN2BinOp.get(func.fqn)
        return None

    def fmt_expr_Call(self, call: ast.Call) -> str:
        if opclass := self.get_binop_maybe(call.func):
            # special case
            assert len(call.args) == 2
            binop = opclass(call.loc, call.args[0], call.args[1])
            return self.fmt_expr_BinOp(binop)
        else:
            # standard case
            name = self.fmt_expr(call.func)
            arglist = [self.fmt_expr(arg) for arg in call.args]
            args = ', '.join(arglist)
            return f'{name}({args})'
