from typing import TYPE_CHECKING

from spy import ast
from spy.errors import SPyError
from spy.fqn import FQN
from spy.location import Loc
from spy.vm.astframe import AbstractFrame
from spy.vm.b import B
from spy.vm.field import W_Field
from spy.vm.function import CLOSURE, W_Func
from spy.vm.object import ClassBody

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


class ClassFrame(AbstractFrame):
    """
    A frame to execute a classdef body
    """

    classdef: ast.ClassDef

    def __init__(
        self, vm: "SPyVM", classdef: ast.ClassDef, ns: FQN, closure: CLOSURE
    ) -> None:
        assert classdef.symtable.kind == "class"
        super().__init__(vm, ns, classdef.loc, classdef.symtable, closure)
        self.classdef = classdef

    def run(self) -> ClassBody:
        self.declare_reserved_bool_locals()

        for stmt in self.classdef.body:
            self.exec_stmt(stmt)

        body = ClassBody(fields_w={}, dict_w={})
        for name, lv in self.locals.items():
            # ignore reserved bool locals
            if name.startswith("@"):
                continue
            if lv.w_val is None:
                # locals declared but not assigned
                body.fields_w[name] = W_Field(name, lv.w_T)
            else:
                body.dict_w[name] = lv.w_val

        return body

    def exec_stmt(self, stmt: ast.Stmt) -> None:
        allowed = (ast.VarDef, ast.If, ast.Pass, ast.FuncDef)
        if type(stmt) in allowed:
            return super().exec_stmt(stmt)

        STMT = type(stmt).__name__
        msg = f"`{STMT}` not supported inside a classdef"
        raise SPyError.simple("W_TypeError", msg, "this is not supported", stmt.loc)

    def exec_stmt_VarDef(self, vardef: ast.VarDef) -> None:
        if vardef.value is not None:
            raise SPyError.simple(
                "W_TypeError",
                "default values in fields not supported yet",
                "this is not supported",
                vardef.value.loc,
            )
        return super().exec_stmt_VarDef(vardef)
