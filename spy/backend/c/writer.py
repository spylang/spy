from py.path import LocalPath
from spy.vm.object import W_Type, W_Object, W_i32
from spy.vm.module import W_Module
from spy.vm.function import W_Function
from spy.vm.codeobject import OpCode
from spy.vm.vm import SPyVM
from spy.textbuilder import TextBuilder
from spy.backend.c.context import Context, C_Type, C_Function
from spy.backend.c import expr as c_expr

class CModuleWriter:
    w_mod: W_Module
    out: TextBuilder

    def __init__(self, vm: SPyVM, w_mod: W_Module) -> None:
        self.ctx = Context(vm)
        self.w_mod = w_mod
        self.out = TextBuilder(use_colors=False)

    def write_c_source(self, outfile: LocalPath) -> None:
        c_src = self.emit_module()
        outfile.write(c_src)

    def emit_module(self) -> str:
        self.out.wl('#include <stdint.h>')
        self.out.wl('#include <stdbool.h>')
        self.out.wl()
        # XXX we should pre-declare variables and functions
        for name, w_obj in self.w_mod.content.values_w.items():
            # XXX we should mangle the name somehow
            if isinstance(w_obj, W_Function):
                self.emit_function(name, w_obj)
            else:
                self.emit_variable(name, w_obj)
        return self.out.build()

    def emit_function(self, name: str, w_func: W_Function) -> None:
        fw = CFuncWriter(self.ctx, self.out, name, w_func)
        fw.emit()

    def emit_variable(self, name: str, w_obj: W_Object) -> None:
        b = self.ctx.vm.builtins
        w_type = self.ctx.vm.dynamic_type(w_obj)
        c_type = self.ctx.w2c(w_type)
        if w_type is b.w_i32:
            intval = self.ctx.vm.unwrap(w_obj)
            self.out.wl(f'{c_type} {name} = {intval};')
        else:
            raise NotImplementedError('WIP')


class CFuncWriter:
    ctx: Context
    name: str
    w_func: W_Function
    tmp_vars: dict[str, C_Type]
    stack: list[c_expr.Expr]

    def __init__(self, ctx: Context, out: TextBuilder, name: str,
                 w_func: W_Function):
        self.ctx = ctx
        self.out = out
        self.name = name
        self.w_func = w_func
        self.tmp_vars = {}
        self.stack = []

    def push(self, expr: c_expr.Expr) -> None:
        assert isinstance(expr, c_expr.Expr)
        self.stack.append(expr)

    def pop(self) -> c_expr.Expr:
        return self.stack.pop()

    def new_var(self, c_type: C_Type) -> str:
        n = len(self.tmp_vars)
        name = f'tmp{n}'
        self.tmp_vars[name] = c_type
        return name

    def emit(self) -> None:
        """
        Emit the code for the whole function
        """
        c_func = self.ctx.c_function(self.name, self.w_func.w_functype)
        self.out.wl(c_func.decl() + ' {')
        with self.out.indent():
            self.emit_local_vars()
            for op in self.w_func.w_code.body:
                self.emit_op(op)
            assert self.stack == []
        self.out.wl('}')

    def emit_local_vars(self):
        """
        Declare all local variables
        """
        param_names = [p.name for p in self.w_func.w_functype.params]
        for varname, w_type in self.w_func.w_code.locals_w_types.items():
            c_type = self.ctx.w2c(w_type)
            if varname not in param_names:
                self.out.wl(f'{c_type} {varname};')

    def emit_op(self, op: OpCode) -> None:
        meth_name = f'emit_op_{op.name}'
        meth = getattr(self, meth_name, None)
        if meth is None:
            raise NotImplementedError(meth_name)
        meth(*op.args)

    def emit_op_load_const(self, w_obj: W_Object) -> None:
        # XXX we need to share code with 'emit_variable'
        b = self.ctx.vm.builtins
        w_type = self.ctx.vm.dynamic_type(w_obj)
        c_type = self.ctx.w2c(w_type)
        if w_type is b.w_void:
            self.push(c_expr.Void())
        elif w_type is b.w_i32:
            intval = self.ctx.vm.unwrap(w_obj)
            self.push(c_expr.Literal(str(intval)))
        else:
            raise NotImplementedError('WIP')

    def emit_op_return(self) -> None:
        expr = self.pop()
        if expr == c_expr.Void():
            # special case for void functions
            self.out.wl('return;')
        else:
            self.out.wl(f'return {expr.str()};')

    def emit_op_abort(self, msg: str) -> None:
        # XXX we ignore it for now
        pass

    def emit_op_load_local(self, varname: str) -> None:
        self.push(c_expr.Literal(varname))

    def emit_op_store_local(self, varname: str) -> None:
        expr = self.pop()
        self.out.wl(f'{varname} = {expr.str()};')

    emit_op_load_global = emit_op_load_local
    emit_op_store_global = emit_op_store_local

    def emit_op_i32_add(self) -> None:
        right = self.pop()
        left = self.pop()
        expr = c_expr.BinOp('+', left, right)
        self.push(expr)
