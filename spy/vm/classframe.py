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
        super().__init__(vm, ns, classdef.loc, classdef.symtable, closure)
        self.classdef = classdef

    def run(self) -> ClassBody:
        # execute field definitions
        self.declare_local("@if", "red", B.w_bool, Loc.fake())
        body = ClassBody(fields_w={}, dict_w={})
        for vardef in self.classdef.fields:
            varname = vardef.name.value
            assert vardef.kind is None
            self.exec_stmt(vardef)
            w_T = self.locals[varname].w_T
            body.fields_w[varname] = W_Field(varname, w_T)

        # execute method definitions
        for stmt in self.classdef.body:
            self.exec_stmt(stmt)

        for name, lv in self.locals.items():
            # ignore variables which were just declared but never assigned; this
            # includes .e.g field declarations
            if lv.w_val is not None:
                body.dict_w[name] = lv.w_val

        return body
