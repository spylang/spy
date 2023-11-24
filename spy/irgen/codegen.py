from typing import NoReturn
from types import NoneType
import spy.ast
from spy.fqn import FQN
from spy.location import Loc
from spy.irgen.typechecker import TypeChecker
from spy.errors import SPyCompileError
from spy.vm.vm import SPyVM, Builtins as B
from spy.vm.object import W_Object
from spy.vm.codeobject import W_CodeObject, OpCode
from spy.vm.function import W_FuncType
from spy.util import magic_dispatch

class LocalVarsComputer:
    funcdef: spy.ast.FuncDef
    locals: set[str]

    def __init__(self, funcdef: spy.ast.FuncDef) -> None:
        self.funcdef = funcdef
        self.locals = set()

    def add(self, name: str) -> None:
        self.locals.add(name)

    def compute(self) -> set[str]:
        for arg in self.funcdef.args:
            self.add(arg.name)
        #
        # XXX this is horribly wrong, because it takes into consideration also
        # the stmts inside inner funcs
        for stmt in self.funcdef.walk(spy.ast.Stmt):
            if isinstance(stmt, spy.ast.Assign):
                import pdb;pdb.set_trace()

        for inner in self.funcdef.walk(spy.ast.FuncDef):
            assert isinstance(inner, spy.ast.FuncDef)
            if inner is self.funcdef:
                continue
            self.add(inner.name)
        #

        # hack hack hack, we need a proper ScopeAnalyzer
        for name in self.funcdef.walk(spy.ast.Name):
            assert isinstance(name, spy.ast.Name)
            if name.id in self.locals:
                name.scope = 'local'

        return self.locals
