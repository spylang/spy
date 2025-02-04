from typing import TYPE_CHECKING
from spy import ast
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
                 fqn: FQN,
                 closure: CLOSURE
                 ) -> None:
        super().__init__(vm, fqn, classdef.symtable, closure)
        self.classdef = classdef

    def run(self) -> ClassBody:
        # execute field definitions
        body = ClassBody(fields={}, methods={})
        for vardef in self.classdef.fields:
            assert vardef.kind == 'var'
            self.exec_stmt_VarDef(vardef)
            body.fields[vardef.name] = self.locals_types_w[vardef.name]

        # execute method definitions
        for funcdef in self.classdef.methods:
            name = funcdef.name
            self.exec_stmt_FuncDef(funcdef)
            w_meth = self.load_local(name)
            assert isinstance(w_meth, W_Func)
            body.methods[name] = w_meth

        return body
