from spy import ast
from spy.fqn import FQN
from spy.analyze.scope import ScopeAnalyzer
from spy.analyze.symtable import SymTable
from spy.errors import SPyError
from spy.vm.vm import SPyVM
from spy.vm.module import W_Module, W_Cell
from spy.vm.object import W_Object
from spy.vm.function import W_ASTFunc
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
        w_builtins = vm.modules_w['builtins']
        super().__init__(vm, ns, symtable, closure=(w_builtins._dict_w,))
        self.mod = mod
        self.w_mod = W_Module(vm, ns.modname, mod.filename)
        self.vm.register_module(self.w_mod)

        # XXX: if we keep this, we SHOULD be able to kill store_local and
        # load_local?
        self._locals = self.w_mod._dict_w # XXXX

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        return f'<{cls} for `{self.ns}`>'

    def store_local(self, name: str, w_value: W_Object) -> None:
        self.w_mod._dict_w[name] = w_value
        #self.w_mod.setattr(name, w_value)

    def load_local(self, name: str) -> W_Object:
        w_obj = self.w_mod._dict_w.get(name)
        #w_obj = self.w_mod.getattr_maybe(name)
        if w_obj is None:
            raise SPyError("W_Exception", 'read from uninitialized local')
        return w_obj

    def run(self) -> W_Module:
        # forward declaration of types
        for decl in self.mod.decls:
            if isinstance(decl, ast.GlobalClassDef):
                self.fwdecl_ClassDef(decl.classdef)

        for decl in self.mod.decls:
            if isinstance(decl, ast.Import):
                self.exec_stmt(decl)
            elif isinstance(decl, ast.GlobalFuncDef):
                self.exec_stmt(decl.funcdef)
            elif isinstance(decl, ast.GlobalClassDef):
                self.exec_stmt(decl.classdef)
            elif isinstance(decl, ast.GlobalVarDef):
                self.gen_GlobalVarDef(decl)
            else:
                assert False
        #
        # call the __INIT__, if present
        w_init = self.w_mod.getattr_maybe('__INIT__')
        if w_init is not None:
            assert isinstance(w_init, W_ASTFunc)
            if w_init.color != "blue":
                err = SPyError(
                    'W_TypeError',
                    "the __INIT__ function must be @blue",
                )
                err.add("error", "function defined here", w_init.def_loc)
                raise err
            self.vm.fast_call(w_init, [self.w_mod])
        #
        return self.w_mod

    def gen_GlobalVarDef(self, decl: ast.GlobalVarDef) -> None:
        vardef = decl.vardef
        assign = decl.assign
        fqn = self.ns.join(vardef.name)
        sym = self.symtable.lookup(vardef.name)
        assert sym.level == 0, 'module assign to name declared outside?'

        # evaluate the vardef in the current frame
        if not isinstance(vardef.type, ast.Auto):
            self.exec_stmt(vardef)

        # evaluate the assignment
        wam = self.eval_expr(assign.value)

        if sym.storage == 'direct':
            self.w_mod._dict_w[sym.name] = wam.w_val
            self.vm.add_global(fqn, wam.w_val) # XXX this should be killed

        elif sym.storage == 'cell':
            w_cell = W_Cell(fqn, wam.w_val)
            self.w_mod._dict_w[sym.name] = w_cell
            self.vm.add_global(fqn, w_cell)

        else:
            assert False
