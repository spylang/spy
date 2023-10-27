import spy.ast
from spy.ast import FQN
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
    modname: str
    mod: spy.ast.Module
    t: TypeChecker

    def __init__(self,
                 vm: SPyVM,
                 t: TypeChecker,
                 modname: str,
                 mod: spy.ast.Module) -> None:
        self.vm = vm
        self.t = t
        self.modname = modname
        self.mod = mod

    def make_w_mod(self) -> W_Module:
        self.w_mod = W_Module(self.vm, self.modname)
        self.vm.register_module(self.w_mod)

        for decl in self.mod.decls:
            if isinstance(decl, spy.ast.FuncDef):
                w_type = self.t.global_scope.lookup_type(decl.name)
                w_func = self.make_w_func(decl)
                name = w_func.w_code.name
                self.vm.add_global(name, w_type, w_func)
            elif isinstance(decl, spy.ast.GlobalVarDef):
                assert isinstance(decl.vardef.value, spy.ast.Constant)
                w_type = self.t.global_scope.lookup_type(decl.vardef.name)
                w_const = self.t.get_w_const(decl.vardef.value)
                self.w_mod.add(decl.vardef.name, w_const, w_type)
        return self.w_mod

    def make_w_func(self, funcdef: spy.ast.FuncDef) -> W_UserFunction:
        name = FQN.from_parts(self.modname, funcdef.name)
        w_functype, scope = self.t.get_funcdef_info(funcdef)
        codegen = CodeGen(self.vm, self.t, name, funcdef)
        w_code = codegen.make_w_code()
        w_func = W_UserFunction(w_code) #, self.w_mod.content)
        return w_func
