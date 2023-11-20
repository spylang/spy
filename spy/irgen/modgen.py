import py
import spy.ast
from spy.fqn import FQN
from spy.irgen.typechecker import TypeChecker
from spy.irgen.codegen import LegacyCodeGen
from spy.irgen.codegen2 import CodeGen
from spy.vm.vm import SPyVM
from spy.vm.module import W_Module
from spy.vm.object import W_Type
from spy.vm.function import W_FuncType, W_UserFunc, W_Func


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
                 mod: spy.ast.Module,
                 file_spy: py.path.local,
                 ) -> None:
        self.vm = vm
        self.t = t
        self.modname = modname
        self.mod = mod
        self.file_spy = file_spy

    def make_w_mod(self) -> W_Module:
        self.w_mod = W_Module(self.vm, self.modname, str(self.file_spy))
        self.vm.register_module(self.w_mod)

        for decl in self.mod.decls:
            if isinstance(decl, spy.ast.FuncDef):
                fqn = FQN(modname=self.modname, attr=decl.name)
                w_type = self.t.global_scope.lookup_type(decl.name)
                assert w_type is not None
                w_func = self.make_w_func(decl)
                self.vm.add_global(fqn, w_type, w_func)
            elif isinstance(decl, spy.ast.GlobalVarDef):
                assert isinstance(decl.vardef.value, spy.ast.Constant)
                fqn = FQN(modname=self.modname, attr=decl.vardef.name)
                w_type = self.t.global_scope.lookup_type(decl.vardef.name)
                assert w_type is not None
                w_const = self.t.get_w_const(decl.vardef.value)
                self.vm.add_global(fqn, w_type, w_const)
        return self.w_mod

    def make_w_func(self, funcdef: spy.ast.FuncDef) -> W_Func:
        if funcdef.color == 'blue':
            codegen = CodeGen(self.vm, self.t, funcdef)
            w_code = codegen.make_w_code()
            return W_UserFunc(w_code) # XXX: should it be W_BlueFunc?
        else:
            w_functype, scope = self.t.get_funcdef_info(funcdef)
            codegen2 = LegacyCodeGen(self.vm, self.t, self.modname, funcdef)
            w_code = codegen2.make_w_code()
            return W_UserFunc(w_code)
