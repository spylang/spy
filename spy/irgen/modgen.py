import py
import spy.ast
from spy.location import Loc
from spy.fqn import FQN
from spy.irgen.typechecker import TypeChecker
from spy.irgen.legacy_codegen import LegacyCodeGen
from spy.irgen.codegen import CodeGen
from spy.vm.vm import SPyVM, Builtins as B
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
    legacy: bool # XXX kill me

    def __init__(self,
                 vm: SPyVM,
                 t: TypeChecker,
                 modname: str,
                 mod: spy.ast.Module,
                 file_spy: py.path.local,
                 legacy: bool,
                 ) -> None:
        self.vm = vm
        self.t = t
        self.modname = modname
        self.mod = mod
        self.file_spy = file_spy
        self.legacy = legacy # XXX kill me

    def make_w_mod(self) -> W_Module:
        self.w_mod = W_Module(self.vm, self.modname, str(self.file_spy))
        self.vm.register_module(self.w_mod)
        if self.legacy:
            # XXX kill me
            self.make_w_mod_legacy()
            return self.w_mod
        #
        w_INIT = self.gen_INIT()
        self.vm.call_function(w_INIT, [])
        return self.w_mod

    def gen_INIT(self) -> W_UserFunc:
        """
        Synthesize the @blue __INIT__ function, which populates the module
        """
        loc = Loc(str(self.file_spy), 1, 1, 1, 1)
        modinit_funcdef = spy.ast.FuncDef(
            loc = loc,
            color = 'blue',
            name = f'__INIT__',
            args = [],
            return_type = spy.ast.Name(loc=loc, id='object'),
            body = []
        )
        self.codegen = CodeGen(self.vm, self.t, modinit_funcdef)
        for decl in self.mod.decls:
            if isinstance(decl, spy.ast.FuncDef):
                self.gen_FuncDef(decl)
            elif isinstance(decl, spy.ast.GlobalVarDef):
                self.gen_GlobalVarDef(decl)
        # epilogue
        self.codegen.emit(loc, 'load_const', B.w_None)
        self.codegen.emit(loc, 'return')
        #
        fqn = FQN(modname=self.modname, attr='__INIT__')
        w_functype = W_FuncType.parse('def() -> void')
        w_func = W_UserFunc(fqn, w_functype, self.codegen.w_code)
        return w_func

    def gen_FuncDef(self, funcdef: spy.ast.FuncDef) -> None:
        fqn = FQN(modname=self.modname, attr=funcdef.name)
        self.codegen.gen_eval_FuncDef(funcdef)
        self.codegen.emit(funcdef.loc, 'add_global', fqn)

    def gen_GlobalVarDef(self, vardef: spy.ast.GlobalVarDef) -> None:
        import pdb;pdb.set_trace()


    # ===== legacy stuff, to kill eventually =====

    def make_w_mod_legacy(self) -> None:
        for decl in self.mod.decls:
            if isinstance(decl, spy.ast.FuncDef):
                fqn = FQN(modname=self.modname, attr=decl.name)
                w_type = self.t.global_scope.lookup_type(decl.name)
                assert w_type is not None
                w_func = self.make_w_func_legacy(decl)
                self.vm.add_global(fqn, w_type, w_func)
            elif isinstance(decl, spy.ast.GlobalVarDef):
                assert isinstance(decl.vardef.value, spy.ast.Constant)
                fqn = FQN(modname=self.modname, attr=decl.vardef.name)
                w_type = self.t.global_scope.lookup_type(decl.vardef.name)
                assert w_type is not None
                w_const = self.t.get_w_const(decl.vardef.value)
                self.vm.add_global(fqn, w_type, w_const)

    def make_w_func_legacy(self, funcdef: spy.ast.FuncDef) -> W_Func:
        assert self.legacy
        assert funcdef.color == 'red'
        w_functype = self.t.funcdef_types[funcdef]
        fqn = FQN(modname=self.modname, attr=funcdef.name)
        w_functype, scope = self.t.get_funcdef_info(funcdef)
        codegen2 = LegacyCodeGen(self.vm, self.t, self.modname, funcdef)
        w_code = codegen2.make_w_code()
        return W_UserFunc(fqn, w_functype, w_code)
