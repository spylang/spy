import py
from spy import ast
from spy.location import Loc
from spy.fqn import FQN
from spy.irgen.scope import ScopeAnalyzer
from spy.irgen.symtable import SymTable
from spy.errors import SPyError
from spy.vm.vm import SPyVM
from spy.vm.b import B
from spy.vm.module import W_Module
from spy.vm.object import W_Type, W_Object
from spy.vm.function import W_FuncType, W_ASTFunc
from spy.vm.astframe import AbstractFrame


class ModFrame(AbstractFrame):
    """
    A frame to execute the body of a module
    """
    vm: SPyVM
    modname: str
    mod: ast.Module
    scopes: ScopeAnalyzer

    def __init__(self,
                 vm: SPyVM,
                 ns: FQN,
                 symtable: SymTable,
                 mod: ast.Module,
                 ) -> None:
        super().__init__(vm, ns, symtable, closure=())
        self.mod = mod

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        return f'<{cls} for `{self.ns}`>'

    def run(self) -> W_Module:
        w_mod = W_Module(self.vm, self.ns.modname, self.mod.filename)
        self.vm.register_module(w_mod)

        # forward declaration of types
        for decl in self.mod.decls:
            if isinstance(decl, ast.GlobalClassDef):
                self.fwdecl_ClassDef(decl.classdef)

        for decl in self.mod.decls:
            if isinstance(decl, ast.Import):
                pass
            elif isinstance(decl, ast.GlobalFuncDef):
                self.exec_stmt_FuncDef(decl.funcdef)
            elif isinstance(decl, ast.GlobalClassDef):
                self.exec_stmt_ClassDef(decl.classdef)
            elif isinstance(decl, ast.GlobalVarDef):
                self.gen_GlobalVarDef(decl)
            else:
                assert False
        #
        # call the __INIT__, if present
        w_init = w_mod.getattr_maybe('__INIT__')
        if w_init is not None:
            assert isinstance(w_init, W_ASTFunc)
            if w_init.color != "blue":
                err = SPyError("the __INIT__ function must be @blue",
                               etype='TypeError')
                err.add("error", "function defined here", w_init.def_loc)
                raise err
            self.vm.fast_call(w_init, [w_mod])
        #
        return w_mod

    def gen_GlobalVarDef(self, decl: ast.GlobalVarDef) -> None:
        vardef = decl.vardef
        assign = decl.assign
        fqn = self.ns.join(vardef.name)

        # evaluate the vardef in the current frame
        if not isinstance(vardef.type, ast.Auto):
            self.exec_stmt_VarDef(vardef)
        self.exec_stmt_Assign(assign)

        # add it to the globals
        w_val = self.load_local(vardef.name)
        self.vm.add_global(fqn, w_val)
