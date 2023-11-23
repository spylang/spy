from typing import NoReturn, Optional
from types import NoneType
import spy.ast
from spy.location import Loc
from spy.errors import SPyTypeError, SPyImportError, maybe_plural
from spy.irgen.symtable import SymTable, Symbol
from spy.irgen import multiop
from spy.vm.vm import SPyVM, Builtins as B
from spy.vm.object import W_Type, W_Object
from spy.vm.function import W_FuncType, FuncParam
from spy.util import magic_dispatch


class ScopeAnalyzer:
    """
    Visit the given AST Module and determine the scope of each name
    """
    vm: SPyVM
    mod: spy.ast.Module
    funcdef_scopes: dict[spy.ast.FuncDef, SymTable]

    def __init__(self, vm: SPyVM, mod: spy.ast.Module) -> None:
        self.vm = vm
        self.mod = mod
        self.builtins_scope = SymTable.from_builtins(vm)
        import pdb;pdb.set_trace()
        self.mod_scope = SymTable(f'{mod.name}::', parent=self.builtins_scope)
        self.funcdef_scopes = {}

    # ===============
    # public API
    # ================

    def run(self) -> None:
        self.visit_Module(self.mod, self.global_scope)
