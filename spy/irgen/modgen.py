from typing import NoReturn
import ast as py_ast
import spy.ast
from spy.parser import Parser
from spy.irgen.codegen import CodeGen
from spy.errors import SPyTypeError, SomeLocation
from spy.vm.vm import SPyVM
from spy.vm.varstorage import VarStorage
from spy.vm.module import W_Module
from spy.vm.object import W_Type
from spy.vm.function import W_FunctionType, W_Function


class ModuleGen:
    """
    Generate a W_Module, given a spy.ast.Module.
    """
    vm: SPyVM
    mod: spy.ast.Module

    def __init__(self, vm: SPyVM, mod: spy.ast.Module) -> None:
        self.vm = vm
        self.mod = mod

    def error(self, loc: SomeLocation, message: str) -> NoReturn:
        raise SPyTypeError(self.mod.filename, loc, message)

    def make_w_mod(self) -> W_Module:
        name = 'mymod' # XXX
        self.w_mod = W_Module(self.vm, name)
        for decl in self.mod.decls:
            assert isinstance(decl, spy.ast.FuncDef)
            w_func = self.make_w_func(decl)
            self.w_mod.add(w_func.w_code.name, w_func)
        return self.w_mod

    def make_w_func(self, funcdef: spy.ast.FuncDef) -> W_Function:
        argtypes_w = [self.resolve_type(arg.type) for arg in funcdef.args]
        w_return_type = self.resolve_type(funcdef.return_type)
        w_functype = W_FunctionType(argtypes_w, w_return_type)

        codegen = CodeGen(self.vm, funcdef, w_functype)
        w_code = codegen.make_w_code()

        w_func = W_Function(w_functype, w_code, self.w_mod.content)
        return w_func

    def resolve_type(self, expr: py_ast.expr) -> W_Type:
        # OK, this is very wrong. We should have a proper table of types with
        # the possibility of nested scopes and lookups. For now, we just to a
        # hardcoded lookup in the VM builtins, which is good enough to resolve
        # builtin types.
        #
        # Also, eventually we should support arbitrary expressions, but for
        # now we just support simple Names.
        if not isinstance(expr, py_ast.Name):
            self.error(expr, f'Only simple types are supported for now')
        #
        w_type = self.vm.builtins.lookup(expr.id)
        if w_type is None:
            self.error(expr, f'Unknown type: {expr.id}')
        if not isinstance(w_type, W_Type):
            self.error(expr, f'{expr.id} is not a type')
        #
        return w_type
