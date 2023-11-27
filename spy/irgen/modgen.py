import py
from spy import ast
from spy.location import Loc
from spy.fqn import FQN
from spy.irgen.scope import ScopeAnalyzer
from spy.irgen.typechecker import TypeChecker
from spy.irgen.legacy_codegen import LegacyCodeGen
from spy.vm.vm import SPyVM, Builtins as B
from spy.vm.module import W_Module
from spy.vm.object import W_Type
from spy.vm.function import W_FuncType, W_UserFunc, W_ASTFunc
from spy.vm.astframe import ASTFrame


class ModuleGen:
    """
    Generate a W_Module, given a ast.Module.
    """
    vm: SPyVM
    modname: str
    mod: ast.Module
    scopes: ScopeAnalyzer
    t: TypeChecker
    legacy: bool # XXX kill me

    def __init__(self,
                 vm: SPyVM,
                 scopes: ScopeAnalyzer,
                 t: TypeChecker,
                 modname: str,
                 mod: ast.Module,
                 file_spy: py.path.local,
                 legacy: bool,
                 ) -> None:
        self.vm = vm
        self.scopes = scopes
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
        # Synthesize and execute the __INIT__ function to populate the module
        modinit_funcdef = self.make_modinit()
        fqn = FQN(modname=self.modname, attr='__INIT__')
        w_functype = W_FuncType.parse('def() -> void')
        w_INIT = W_ASTFunc(fqn, self.modname, w_functype, modinit_funcdef)
        frame = ASTFrame(self.vm, w_INIT)
        #
        for decl in self.mod.decls:
            if isinstance(decl, ast.GlobalFuncDef):
                self.gen_FuncDef(frame, decl.funcdef)
            elif isinstance(decl, ast.GlobalVarDef):
                self.gen_GlobalVarDef(frame, decl.vardef)
        #
        return self.w_mod

    def make_modinit(self) -> ast.FuncDef:
        loc = Loc(str(self.file_spy), 1, 1, 1, 1)
        return ast.FuncDef(
            loc = loc,
            color = 'blue',
            name = f'__INIT__',
            args = [],
            return_type = ast.Name(loc=loc, id='object'),
            body = []
        )

    def gen_FuncDef(self, frame: ASTFrame, funcdef: ast.FuncDef) -> None:
        fqn = FQN(modname=self.modname, attr=funcdef.name)
        frame.exec_stmt_FuncDef(funcdef)
        w_func = frame.locals.get(funcdef.name)
        self.vm.add_global(fqn, None, w_func)

    def gen_GlobalVarDef(self, frame: ASTFrame, vardef: ast.VarDef) -> None:
        fqn = FQN(modname=self.modname, attr=vardef.name)
        w_type = frame.eval_expr(vardef.type)
        w_value = frame.eval_expr(vardef.value)
        self.vm.add_global(fqn, w_type, w_value)

    # ===== legacy stuff, to kill eventually =====

    def make_w_mod_legacy(self) -> None:
        for decl in self.mod.decls:
            if isinstance(decl, ast.GlobalFuncDef):
                name = decl.funcdef.name
                fqn = FQN(modname=self.modname, attr=name)
                w_type = self.t.global_scope.lookup_type(name)
                assert w_type is not None
                w_func = self.make_w_func_legacy(decl.funcdef)
                self.vm.add_global(fqn, w_type, w_func)
            elif isinstance(decl, ast.GlobalVarDef):
                assert isinstance(decl.vardef.value, ast.Constant)
                fqn = FQN(modname=self.modname, attr=decl.vardef.name)
                w_type = self.t.global_scope.lookup_type(decl.vardef.name)
                assert w_type is not None
                w_const = self.t.get_w_const(decl.vardef.value)
                self.vm.add_global(fqn, w_type, w_const)

    def make_w_func_legacy(self, funcdef: ast.FuncDef) -> W_UserFunc:
        assert self.legacy
        assert funcdef.color == 'red'
        w_functype = self.t.funcdef_types[funcdef]
        fqn = FQN(modname=self.modname, attr=funcdef.name)
        w_functype, scope = self.t.get_funcdef_info(funcdef)
        codegen = LegacyCodeGen(self.vm, self.t, self.modname, funcdef)
        w_code = codegen.make_w_code()
        w_func = W_UserFunc(fqn, w_functype, w_code)
        return w_func
