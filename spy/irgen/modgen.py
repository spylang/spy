import spy.ast
from spy.irgen.typechecker import TypeChecker
from spy.irgen.codegen import CodeGen
from spy.vm.vm import SPyVM
from spy.vm.module import W_Module
from spy.vm.object import W_Type
from spy.vm.function import W_FunctionType, W_UserFunction


class ModuleGen:
    """
    Generate a W_Module, given a spy.ast.Module.
    """
    vm: SPyVM
    mod: spy.ast.Module
    t: TypeChecker

    def __init__(self, vm: SPyVM, t: TypeChecker, mod: spy.ast.Module) -> None:
        self.vm = vm
        self.t = t
        self.mod = mod

    def make_w_mod(self) -> W_Module:
        name = 'mymod' # XXX
        self.w_mod = W_Module(self.vm, name)
        for decl in self.mod.decls:
            if isinstance(decl, spy.ast.FuncDef):
                w_func = self.make_w_func(decl)
                self.w_mod.add(w_func.w_code.name, w_func)
            elif isinstance(decl, spy.ast.GlobalVarDef):
                assert isinstance(decl.vardef.value, spy.ast.Constant)
                w_const = self.t.get_w_const(decl.vardef.value)
                self.w_mod.add(decl.vardef.name, w_const)
        return self.w_mod

    def make_w_func(self, funcdef: spy.ast.FuncDef) -> W_UserFunction:
        w_functype, scope = self.t.get_funcdef_info(funcdef)
        codegen = CodeGen(self.vm, self.t, funcdef)
        w_code = codegen.make_w_code()
        w_func = W_UserFunction(w_code, self.w_mod.content)
        return w_func
