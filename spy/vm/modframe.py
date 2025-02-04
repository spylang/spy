import py
from spy import ast
from spy.location import Loc
from spy.fqn import FQN
from spy.irgen.scope import ScopeAnalyzer
from spy.irgen.symtable import SymTable
from spy.errors import SPyTypeError
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
                 fqn: FQN,
                 symtable: SymTable,
                 mod: ast.Module,
                 ) -> None:
        super().__init__(vm, fqn, symtable, closure=())
        self.mod = mod

    def run(self) -> W_Module:
        w_mod = W_Module(self.vm, self.fqn.modname, self.mod.filename)
        self.vm.register_module(w_mod)

        # forward declaration of types
        for decl in self.mod.decls:
            if isinstance(decl, ast.GlobalClassDef):
                type_fqn = self.fqn.join(decl.classdef.name)
                pyclass = self.metaclass_for_classdef(decl.classdef)
                w_typedecl = pyclass.declare(type_fqn)
                w_meta_type = self.vm.dynamic_type(w_typedecl)
                self.declare_local(decl.classdef.name, w_meta_type)
                self.store_local(decl.classdef.name, w_typedecl)
                self.vm.add_global(type_fqn, w_typedecl)

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
            assert w_init.color == "blue"
            self.vm.fast_call(w_init, [w_mod])
        #
        return w_mod

    def gen_GlobalVarDef(self, decl: ast.GlobalVarDef) -> None:
        vardef = decl.vardef
        assign = decl.assign
        fqn = self.fqn.join(vardef.name)
        if isinstance(vardef.type, ast.Auto):
            # type inference
            wop = self.eval_expr(assign.value)
            self.vm.add_global(fqn, wop.w_val)
        else:
            # eval the type and use it in the globals declaration
            w_type = self.eval_expr_type(vardef.type)
            wop = self.eval_expr(assign.value)
            assert self.vm.isinstance(wop.w_val, w_type)
            self.vm.add_global(fqn, wop.w_val)
