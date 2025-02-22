from typing import Literal, Optional
from spy import ast
from spy.fqn import FQN
from spy.vm.vm import SPyVM
from spy.vm.object import W_Object, W_Type
from spy.vm.function import W_ASTFunc, FuncParam
from spy.vm.list import W_List
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
        # these are initialized by dump_w_func
        self.w_func: W_ASTFunc = None       # type: ignore
        self.vars_declared: set[str] = None # type: ignore

    def dump_mod(self, modname: str) -> str:
        w_mod = self.vm.modules_w[modname]
        for fqn, w_obj in w_mod.items_w():
            if isinstance(w_obj, W_ASTFunc) and w_obj.color == 'red':
                self.dump_w_func(fqn, w_obj)
                self.out.wl()
        return self.out.build()

    def dump_w_func(self, fqn: FQN, w_func: W_ASTFunc) -> None:
        if fqn.suffix == '':
            # this is a global function, we can just use its name
            name = fqn.symbol_name
        else:
            name = self.fmt_fqn(fqn)
        self.w_func = w_func
        self.vars_declared = set()
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
        if isinstance(w_obj, W_Type) and issubclass(w_obj.pyclass, W_List):
            # this is a ugly special case for now, we need to find a better
            # solution
            return w_obj.fqn.human_name
        #
        # this assumes that w_obj has a valid FQN
        fqn = self.vm.reverse_lookup_global(w_obj)
        assert fqn is not None
        return self.fmt_fqn(fqn)

    def fmt_fqn(self, fqn: FQN) -> str:
        if self.fqn_format == 'no':
            return fqn.symbol_name # don't show the namespace
        elif self.fqn_format == 'short' and fqn.modname == 'builtins':
            return fqn.symbol_name # don't show builtins::
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

    def emit_declare_var_maybe(self, varname: str) -> None:
        if self.w_func.redshifted and varname not in self.vars_declared:
            assert self.w_func.locals_types_w is not None
            w_type = self.w_func.locals_types_w[varname]
            t = self.fmt_w_obj(w_type)
            self.wl(f'{varname}: {t}')
            self.vars_declared.add(varname)

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

    def emit_stmt_ClassDef(self, classdef: ast.ClassDef) -> None:
        assert classdef.kind == 'struct', 'IMPLEMENT ME'
        name = classdef.name
        self.wl('@struct')
        self.wl(f'class {name}:')
        with self.out.indent():
            for field in classdef.fields:
                self.emit_stmt_VarDef(field)

    def emit_stmt_Pass(self, stmt: ast.Pass) -> None:
        self.wl('pass')

    def emit_stmt_Return(self, ret: ast.Return) -> None:
        v = self.fmt_expr(ret.value)
        self.wl(f'return {v}')

    def emit_stmt_Assign(self, assign: ast.Assign) -> None:
        varname = assign.target.value
        self.emit_declare_var_maybe(varname)
        v = self.fmt_expr(assign.value)
        self.wl(f'{varname} = {v}')

    def emit_stmt_UnpackAssign(self, unpack: ast.UnpackAssign) -> None:
        targets = ', '.join([t.value for t in unpack.targets])
        v = self.fmt_expr(unpack.value)
        self.wl(f'{targets} = {v}')

    def emit_stmt_SetAttr(self, node: ast.SetAttr) -> None:
        t = self.fmt_expr(node.target)
        a = node.attr.value
        v = self.fmt_expr(node.value)
        self.wl(f'{t}.{a} = {v}')

    def emit_stmt_SetItem(self, node: ast.SetItem) -> None:
        t = self.fmt_expr(node.target)
        i = self.fmt_expr(node.index)
        v = self.fmt_expr(node.value)
        self.wl(f'{t}[i] = {v}')

    def emit_stmt_VarDef(self, vardef: ast.VarDef) -> None:
        t = self.fmt_expr(vardef.type)
        self.wl(f'{vardef.name}: {t}')
        self.vars_declared.add(vardef.name)

    def emit_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> None:
        v = self.fmt_expr(stmt.value)
        self.wl(f'{v}')

    def emit_stmt_While(self, while_node: ast.While) -> None:
        test = self.fmt_expr(while_node.test)
        self.wl(f'while {test}:')
        with self.out.indent():
            for stmt in while_node.body:
                self.emit_stmt(stmt)

    def emit_stmt_If(self, if_node: ast.If) -> None:
        test = self.fmt_expr(if_node.test)
        self.wl(f'if {test}:')
        with self.out.indent():
            for stmt in if_node.then_body:
                self.emit_stmt(stmt)
        if if_node.else_body:
            self.wl('else:')
            with self.out.indent():
                for stmt in if_node.else_body:
                    self.emit_stmt(stmt)

    # expressions

    def fmt_expr_Constant(self, const: ast.Constant) -> str:
        return repr(const.value)

    def fmt_expr_StrConst(self, const: ast.StrConst) -> str:
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
    fmt_expr_Mod = fmt_expr_BinOp
    fmt_expr_LShift = fmt_expr_BinOp
    fmt_expr_RShift = fmt_expr_BinOp
    fmt_expr_BitAnd = fmt_expr_BinOp
    fmt_expr_BitOr = fmt_expr_BinOp
    fmt_expr_BitXor = fmt_expr_BinOp
    fmt_expr_Eq = fmt_expr_BinOp
    fmt_expr_NotEq = fmt_expr_BinOp
    fmt_expr_Lt = fmt_expr_BinOp
    fmt_expr_LtE = fmt_expr_BinOp
    fmt_expr_Gt = fmt_expr_BinOp
    fmt_expr_GtE = fmt_expr_BinOp

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
        opclass = self.get_binop_maybe(call.func)
        if self.fqn_format == 'short' and opclass:
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

    def fmt_expr_CallMethod(self, callm: ast.CallMethod) -> str:
        t = self.fmt_expr(callm.target)
        m = callm.method.value
        arglist = [self.fmt_expr(arg) for arg in callm.args]
        args = ', '.join(arglist)
        return f'{t}.{m}({args})'

    def fmt_expr_GetItem(self, getitem: ast.GetItem) -> str:
        v = self.fmt_expr(getitem.value)
        i = self.fmt_expr(getitem.index)
        return f'{v}[{i}]'

    def fmt_expr_GetAttr(self, node: ast.GetAttr) -> str:
        v = self.fmt_expr(node.value)
        return f'{v}.{node.attr.value}'

    def fmt_expr_List(self, node: ast.List) -> str:
        itemlist = [self.fmt_expr(it) for it in node.items]
        items = ', '.join(itemlist)
        return f'[{items}]'

    def fmt_expr_Tuple(self, node: ast.Tuple) -> str:
        itemlist = [self.fmt_expr(it) for it in node.items]
        items = ', '.join(itemlist)
        return f'({items})'
