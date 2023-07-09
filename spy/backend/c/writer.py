from dataclasses import dataclass
from py.path import LocalPath
from spy.vm.vm import SPyVM
from spy.vm.object import W_Type, W_Object, W_i32
from spy.vm.module import W_Module
from spy.vm.function import W_Function
from spy.vm.codeobject import OpCode
from spy.textbuilder import TextBuilder


@dataclass
class C_Type:
    """
    A C type.

    Just a tiny wrapper around a string, but it helps to make things tidy.
    """
    name: str

    def __repr__(self) -> str:
        return f"<C type '{self.name}'>"

    def __str__(self) -> str:
        return self.name

@dataclass
class C_FuncParam:
    name: str
    c_type: C_Type


@dataclass
class C_Function:
    name: str
    params: list[C_FuncParam]
    c_restype: C_Type

    def __repr__(self) -> str:
        return f"<C func '{self.name}'>"

    def __str__(self) -> str:
        if self.params == []:
            s_params = 'void'
        else:
            paramlist = [f'{p.c_type} {p.name}' for p in self.params]
            s_params = ', '.join(paramlist)
        #
        return f'{self.c_restype} {self.name}({s_params})'



class TypeManager:
    _d: dict[W_Type, C_Type]

    def __init__(self, vm: SPyVM) -> None:
        self._d = {}
        b = vm.builtins
        self._d[b.w_i32] = C_Type('int32_t')
        self._d[b.w_bool] = C_Type('bool')

    def w2c(self, w_type: W_Type) -> C_Type:
        if w_type in self._d:
            return self._d[w_type]
        raise NotImplementedError(f'Cannot translate type {w_type} to C')


class CModuleWriter:
    vm: SPyVM
    w_mod: W_Module
    c: TextBuilder
    types: TypeManager

    def __init__(self, vm: SPyVM, w_mod: W_Module) -> None:
        self.vm = vm
        self.w_mod = w_mod
        self.c = TextBuilder(use_colors=False)
        self.types = TypeManager(vm)

    def write_c_source(self, outfile: LocalPath) -> None:
        c_src = self.generate_c_file()
        outfile.write(c_src)

    def generate_c_file(self) -> str:
        self.c.wl('#include <stdint.h>')
        self.c.wl('#include <stdbool.h>')
        self.c.wl()
        # XXX we should pre-declare variables and functions
        for name, w_obj in self.w_mod.content.values_w.items():
            # XXX we should mangle the name somehow
            if isinstance(w_obj, W_Function):
                func_builder = CFuncBuilder(self)
                func_builder.write(name, w_obj)
            else:
                raise NotImplementedError('WIP')
        #
        return self.c.build()


class CFuncBuilder:
    builder: CModuleWriter

    def __init__(self, builder: CModuleWriter):
        self.builder = builder
        self.vm = builder.vm
        self.types = builder.types
        self.c = builder.c
        self.tmp_vars = {}
        self.local_vars = {}  # dict[str, C_Type]
        self.stack = []

    def new_var(self, c_type: C_Type) -> str:
        n = len(self.tmp_vars)
        name = f'tmp{n}'
        self.tmp_vars[name] = c_type
        return name

    def write(self, name: str, w_func: W_Function) -> None:
        w2c = self.builder.types.w2c
        w_functype = w_func.w_functype
        c_restype = w2c(w_functype.w_restype)
        c_params = []
        param_names = set()
        for p in w_functype.params:
            c_param = C_FuncParam(name=p.name, c_type=w2c(p.w_type))
            c_params.append(c_param)
            param_names.add(p.name)
        c_func = C_Function(name, c_params, c_restype)
        self.c.wl(str(c_func) + ' {')
        #
        for varname, w_type in w_func.w_code.locals_w_types.items():
            c_type = self.types.w2c(w_type)
            self.local_vars[varname] = c_type
            if varname not in param_names:
                self.c.wl(f'    {c_type} {varname};')
        for op in w_func.w_code.body:
            self.write_op(op)
        self.c.wl('}')

    def write_op(self, op: OpCode) -> None:
        meth_name = f'write_op_{op.name}'
        meth = getattr(self, meth_name, None)
        if meth is None:
            raise NotImplementedError(meth_name)
        meth(*op.args)

    def write_op_load_const(self, w_const: W_Object) -> None:
        w_type = self.vm.dynamic_type(w_const)
        c_type = self.types.w2c(w_type)
        tmpvar = self.new_var(c_type)
        assert isinstance(w_const, W_i32), 'WIP'
        intval = self.vm.unwrap(w_const)
        self.c.wl(f'    {c_type} {tmpvar} = {intval};')
        self.stack.append(tmpvar)

    def write_op_return(self) -> None:
        tmpvar = self.stack.pop()
        self.c.wl(f'    return {tmpvar};')

    def write_op_abort(self, msg: str) -> None:
        # XXX we ignore it for now
        pass

    def write_op_load_local(self, varname: str) -> None:
        self.stack.append(varname)

    def write_op_store_local(self, varname: str) -> None:
        tmpvar = self.stack.pop()
        self.c.wl(f'    {varname} = {tmpvar};')

    def write_op_i32_add(self) -> None:
        t = C_Type('int32_t')
        right = self.stack.pop()
        left = self.stack.pop()
        tmp = self.new_var(t)
        self.c.wl(f'    {t} {tmp} = {left} + {right};')
        self.stack.append(tmp)
