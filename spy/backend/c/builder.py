from dataclasses import dataclass
from typing import TextIO, Any
from py.path import LocalPath
from spy.vm.vm import SPyVM
from spy.vm.object import W_Type, W_Object, W_i32
from spy.vm.module import W_Module
from spy.vm.function import W_Function
from spy.vm.codeobject import OpCode
from spy.util import magic_dispatch

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


class CModuleBuilder:
    vm: SPyVM
    w_mod: W_Module
    outdir: LocalPath
    outfile: LocalPath
    f: TextIO

    def __init__(self, vm: SPyVM, w_mod: W_Module, outdir: LocalPath) -> None:
        self.vm = vm
        self.w_mod = w_mod
        self.outdir = outdir
        self.outfile = self.outdir.join(f'{w_mod.name}.c')
        self.types = TypeManager(vm)

    def w(self, *args: Any, end: str = '\n') -> None:
        print(*args, file=self.f, end=end)

    def write_source(self) -> None:
        with self.outfile.open('w') as self.f:
            self.w('#include <stdint>')
            self.w('#include <stdbool>')
            self.w()
            # XXX we should pre-declare variables and functions
            for name, w_obj in self.w_mod.content.values_w.items():
                # XXX we should mangle the name somehow
                if isinstance(w_obj, W_Function):
                    func_builder = CFuncBuilder(self)
                    func_builder.write(name, w_obj)
                else:
                    raise NotImplementedError('WIP')



class CFuncBuilder:
    builder: CModuleBuilder

    def __init__(self, builder: CModuleBuilder):
        self.builder = builder
        self.vm = builder.vm
        self.types = builder.types
        self.tmp_vars = {}
        self.stack = []

    def new_var(self, c_type: C_Type) -> str:
        n = len(self.tmp_vars)
        name = f'tmp{n}'
        self.tmp_vars[name] = c_type
        return name

    def w(self, *args: Any, end: str = '\n') -> None:
        print(*args, file=self.builder.f, end=end)

    def write(self, name: str, w_func: W_Function) -> None:
        w2c = self.builder.types.w2c
        w_functype = w_func.w_functype
        c_restype = w2c(w_functype.w_restype)
        c_params = [C_FuncParam(name=p.name, c_type=w2c(p.w_type))
                    for p in w_functype.params]
        c_func = C_Function(name, c_params, c_restype)
        self.w(c_func, '{')
        for op in w_func.w_code.body:
            self.write_op(op)
        self.w('}')

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
        self.w(f'    {c_type} {tmpvar} = {intval};')
        self.stack.append(tmpvar)

    def write_op_return(self) -> None:
        tmpvar = self.stack.pop()
        self.w(f'    return {tmpvar};')

    def write_op_abort(self, msg: str) -> None:
        # XXX we ignore it for now
        pass
