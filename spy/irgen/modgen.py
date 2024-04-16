import py
from spy import ast
from spy.location import Loc
from spy.fqn import QN
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
        # Synthesize and execute the fake '@module' function to populate the mod
        w_functype = W_FuncType.parse('def() -> void')
        qn = QN(modname=self.modname, attr='@module')
        modinit_funcdef = self.make_modinit()
        closure = ()
        w_INIT = W_ASTFunc(w_functype, qn, modinit_funcdef, closure)
        frame = ASTFrame(self.vm, w_INIT)
        #
        for decl in self.mod.decls:
            if isinstance(decl, ast.GlobalFuncDef):
                self.gen_FuncDef(frame, decl.funcdef)
            elif isinstance(decl, ast.GlobalVarDef):
                self.gen_GlobalVarDef(frame, decl)
        #
        # call the __INIT__, if present
        w_init = self.w_mod.getattr_maybe('__INIT__')
        if w_init is not None:
            assert isinstance(w_init, W_ASTFunc)
            assert w_init.color == "blue"
            self.vm.call_function(w_init, [self.w_mod])
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

    def gen_GlobalVarDef(self, frame: ASTFrame, decl: ast.GlobalVarDef) -> None:
        vardef = decl.vardef
        assign = decl.assign
        fqn = self.vm.get_FQN(QN(modname=self.modname, attr=vardef.name),
                              is_global=True)
        if isinstance(vardef.type, ast.Auto):
            # type inference
            w_val = frame.eval_expr(assign.value)
            self.vm.add_global(fqn, None, w_val)
        else:
            # eval the type and use it in the globals declaration
            w_type = frame.eval_expr_type(vardef.type)
            w_val = frame.eval_expr(assign.value)
            self.vm.add_global(fqn, w_type, w_val)
