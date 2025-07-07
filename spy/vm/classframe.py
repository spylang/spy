from typing import TYPE_CHECKING
from spy import ast
from spy.errors import SPyError
from spy.fqn import FQN
from spy.vm.object import ClassBody
from spy.vm.astframe import AbstractFrame
from spy.vm.function import W_Func, CLOSURE

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
        body = ClassBody(fields={}, methods={})
        for vardef in self.classdef.fields:
            assert vardef.kind == 'var'
            self.exec_stmt(vardef)
            body.fields[vardef.name] = self.locals_types_w[vardef.name]

        # execute method definitions
        for stmt in self.classdef.body:
            self.exec_stmt(stmt)

        for name, w_val in self._locals.items():
            if isinstance(w_val, W_Func):
                body.methods[name] = w_val
            else:
                msg = ('Only field decls and methods are allowed ' +
                       'inside a classdef')
                raise SPyError.simple(
                    'W_WIP', msg, 'class defined here', self.classdef.loc
                )

        return body
