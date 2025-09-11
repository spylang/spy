from typing import TYPE_CHECKING
from spy import ast
from spy.location import Loc
from spy.errors import SPyError
from spy.fqn import FQN
from spy.vm.b import B
from spy.vm.object import ClassBody
from spy.vm.astframe import AbstractFrame
from spy.vm.function import W_Func, CLOSURE
from spy.vm.field import W_Field

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


class ClassFrame(AbstractFrame):
    """
    A frame to execute a classdef body
    """
    classdef: ast.ClassDef

    def __init__(self,
                 vm: 'SPyVM',
                 classdef: ast.ClassDef,
                 ns: FQN,
                 closure: CLOSURE
                 ) -> None:
        super().__init__(vm, ns, classdef.symtable, closure)
        self.classdef = classdef

    def run(self) -> ClassBody:
        # execute field definitions
        self.declare_local('@if', B.w_bool, Loc.fake())
        body = ClassBody(fields_w={}, dict_w={})
        for vardef in self.classdef.fields:
            assert vardef.kind == 'var'
            self.exec_stmt(vardef)
            w_T = self.locals_types_w[vardef.name]
            body.fields_w[vardef.name] = W_Field(vardef.name, w_T)

        # execute method definitions
        for stmt in self.classdef.body:
            self.exec_stmt(stmt)

        for name, w_val in self._locals.items():
            body.dict_w[name] = w_val

        return body
