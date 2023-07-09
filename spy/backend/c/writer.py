from py.path import LocalPath
from spy.vm.object import W_Type, W_Object, W_i32
from spy.vm.module import W_Module
from spy.vm.function import W_Function
from spy.vm.codeobject import OpCode
from spy.vm.vm import SPyVM
from spy.textbuilder import TextBuilder
from spy.backend.c.context import Context, C_Type, C_Function, C_FuncParam

class CModuleWriter:
    w_mod: W_Module
    out: TextBuilder

    def __init__(self, vm: SPyVM, w_mod: W_Module) -> None:
        self.ctx = Context(vm)
        self.w_mod = w_mod
        self.out = TextBuilder(use_colors=False)

    def write_c_source(self, outfile: LocalPath) -> None:
        c_src = self.generate_c_file()
        outfile.write(c_src)

    def generate_c_file(self) -> str:
        self.out.wl('#include <stdint.h>')
        self.out.wl('#include <stdbool.h>')
        self.out.wl()
        # XXX we should pre-declare variables and functions
        for name, w_obj in self.w_mod.content.values_w.items():
            # XXX we should mangle the name somehow
            if isinstance(w_obj, W_Function):
                func_builder = CFuncBuilder(self.ctx, self.out)
                func_builder.write(name, w_obj)
            else:
                raise NotImplementedError('WIP')
        #
        return self.out.build()


class CFuncBuilder:
    ctx: Context
    tmp_vars: dict[str, C_Type]
    local_vars: dict[str, C_Type]
    stack: list[str]

    def __init__(self, ctx: Context, out: TextBuilder):
        self.ctx = ctx
        self.out = out
        self.tmp_vars = {}
        self.local_vars = {}
        self.stack = []

    def new_var(self, c_type: C_Type) -> str:
        n = len(self.tmp_vars)
        name = f'tmp{n}'
        self.tmp_vars[name] = c_type
        return name

    def write(self, name: str, w_func: W_Function) -> None:
        w2c = self.ctx.w2c
        w_functype = w_func.w_functype
        c_restype = w2c(w_functype.w_restype)
        c_params = []
        param_names = set()
        for p in w_functype.params:
            c_param = C_FuncParam(name=p.name, c_type=w2c(p.w_type))
            c_params.append(c_param)
            param_names.add(p.name)
        c_func = C_Function(name, c_params, c_restype)
        self.out.wl(str(c_func) + ' {')
        #
        for varname, w_type in w_func.w_code.locals_w_types.items():
            c_type = self.ctx.w2c(w_type)
            self.local_vars[varname] = c_type
            if varname not in param_names:
                self.out.wl(f'    {c_type} {varname};')
        for op in w_func.w_code.body:
            self.write_op(op)
        self.out.wl('}')

    def write_op(self, op: OpCode) -> None:
        meth_name = f'write_op_{op.name}'
        meth = getattr(self, meth_name, None)
        if meth is None:
            raise NotImplementedError(meth_name)
        meth(*op.args)

    def write_op_load_const(self, w_const: W_Object) -> None:
        w_type = self.ctx.vm.dynamic_type(w_const)
        c_type = self.ctx.w2c(w_type)
        tmpvar = self.new_var(c_type)
        assert isinstance(w_const, W_i32), 'WIP'
        intval = self.ctx.vm.unwrap(w_const)
        self.out.wl(f'    {c_type} {tmpvar} = {intval};')
        self.stack.append(tmpvar)

    def write_op_return(self) -> None:
        tmpvar = self.stack.pop()
        self.out.wl(f'    return {tmpvar};')

    def write_op_abort(self, msg: str) -> None:
        # XXX we ignore it for now
        pass

    def write_op_load_local(self, varname: str) -> None:
        self.stack.append(varname)

    def write_op_store_local(self, varname: str) -> None:
        tmpvar = self.stack.pop()
        self.out.wl(f'    {varname} = {tmpvar};')

    def write_op_i32_add(self) -> None:
        t = C_Type('int32_t')
        right = self.stack.pop()
        left = self.stack.pop()
        tmp = self.new_var(t)
        self.out.wl(f'    {t} {tmp} = {left} + {right};')
        self.stack.append(tmp)
