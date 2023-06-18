import spy.ast
from spy.parser import Parser
from spy.irgen.codegen import CodeGen
from spy.vm.vm import SPyVM
from spy.vm.varstorage import VarStorage
from spy.vm.module import W_Module
from spy.vm.function import W_FunctionType, W_Function


class ModuleGen:
    vm: SPyVM
    mod: spy.ast.Module

    def __init__(self, vm: SPyVM, mod: spy.ast.Module) -> None:
        self.vm = vm
        self.mod = mod

    def make_w_mod(self) -> W_Module:
        name = 'mymod' # XXX
        self.w_mod = W_Module(self.vm, name)
        for decl in self.mod.decls:
            assert isinstance(decl, spy.ast.FuncDef)
            w_func = self.make_w_func(decl)
            self.w_mod.add(w_func.w_code.name, w_func)
        return self.w_mod

    def make_w_func(self, funcdef: spy.ast.FuncDef) -> W_Function:
        codegen = CodeGen(self.vm, funcdef)
        w_code = codegen.make_w_code()
        w_functype = W_FunctionType([], self.vm.builtins.w_i32) # XXX hardcoded
        w_func = W_Function(w_functype, w_code, self.w_mod.content)
        return w_func
