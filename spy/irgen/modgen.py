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
from spy.vm.object import W_Type
from spy.vm.function import W_FuncType, W_ASTFunc
from spy.vm.astframe import ASTFrame


class ModuleGen:
    """
    Generate a W_Module, given a ast.Module.
    """
    vm: SPyVM
    modname: str
    mod: ast.Module
    scopes: ScopeAnalyzer

    def __init__(self,
                 vm: SPyVM,
                 scopes: ScopeAnalyzer,
                 modname: str,
                 mod: ast.Module,
                 file_spy: py.path.local,
                 ) -> None:
        self.vm = vm
        self.scopes = scopes
        self.modname = modname
        self.mod = mod
        self.file_spy = file_spy

    def make_w_mod(self) -> W_Module:
        self.w_mod = W_Module(self.vm, self.modname, str(self.file_spy))
        self.vm.register_module(self.w_mod)
        #
        # Synthesize and execute a function where to evaluate module-level
        # declarations.
        w_functype = W_FuncType.parse('def() -> void')
        qn = FQN(self.modname)
        modinit_funcdef = self.make_modinit()
        closure = ()
        w_INIT = W_ASTFunc(w_functype, qn, modinit_funcdef, closure)
        frame = ASTFrame(self.vm, w_INIT)
        #
        for decl in self.mod.decls:
            if isinstance(decl, ast.Import):
                pass
            elif isinstance(decl, ast.GlobalFuncDef):
                self.gen_FuncDef(frame, decl.funcdef)
            elif isinstance(decl, ast.GlobalClassDef):
                self.gen_ClassDef(frame, decl.classdef)
            elif isinstance(decl, ast.GlobalVarDef):
                self.gen_GlobalVarDef(frame, decl)
            else:
                assert False
        #
        # call the __INIT__, if present
        w_init = self.w_mod.getattr_maybe('__INIT__')
        if w_init is not None:
            assert isinstance(w_init, W_ASTFunc)
            assert w_init.color == "blue"
            self.vm.call(w_init, [self.w_mod])
        #
        return self.w_mod

    def make_modinit(self) -> ast.FuncDef:
        loc = Loc(str(self.file_spy), 1, 1, 1, 1)
        return ast.FuncDef(
            loc = loc,
            color = 'blue',
            name = f'@module',
            args = [],
            return_type = ast.Name(loc=loc, id='object'),
            body = [],
            symtable = self.scopes.by_module(),
        )

    def gen_FuncDef(self, frame: ASTFrame, funcdef: ast.FuncDef) -> None:
        # sanity check: if it's the global __INIT__, it must be @blue
        if funcdef.name == '__INIT__' and funcdef.color != 'blue':
            err = SPyTypeError("the __INIT__ function must be @blue")
            err.add("error", "function defined here", funcdef.prototype_loc)
            raise err
        frame.exec_stmt_FuncDef(funcdef)
        w_func = frame.load_local(funcdef.name)
        assert isinstance(w_func, W_ASTFunc)
        fqn = self.vm.get_FQN(w_func.qn, is_global=True)
        self.vm.add_global(fqn, None, w_func)

    def gen_ClassDef(self, frame: ASTFrame, classdef: ast.ClassDef) -> None:
        frame.exec_stmt_ClassDef(classdef)
        w_class = frame.load_local(classdef.name)
        assert isinstance(w_class, W_Type)
        qn = FQN([self.modname, classdef.name])
        fqn = self.vm.get_FQN(qn, is_global=True)
        self.vm.add_global(fqn, None, w_class)

    def gen_GlobalVarDef(self, frame: ASTFrame, decl: ast.GlobalVarDef) -> None:
        vardef = decl.vardef
        assign = decl.assign
        qn = FQN([self.modname, vardef.name])
        fqn = self.vm.get_FQN(qn, is_global=True)
        if isinstance(vardef.type, ast.Auto):
            # type inference
            w_val = frame.eval_expr(assign.value)
            self.vm.add_global(fqn, None, w_val)
        else:
            # eval the type and use it in the globals declaration
            w_type = frame.eval_expr_type(vardef.type)
            w_val = frame.eval_expr(assign.value)
            self.vm.add_global(fqn, w_type, w_val)
