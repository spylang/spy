from typing import TYPE_CHECKING

from spy import ast
from spy.errors import SPyError
from spy.fqn import FQN
from spy.location import Loc
from spy.vm.astframe import AbstractFrame
from spy.vm.b import B
from spy.vm.field import W_Field
from spy.vm.function import CLOSURE, W_Func
from spy.vm.modules.__spy__ import SPY
from spy.vm.object import ClassBody, W_Type

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

    def __repr__(self) -> str:
        return f"ClassFrame(name='{self.classdef.name}' kind='{self.classdef.kind}')"

    def run(self) -> ClassBody:
        self.declare_reserved_bool_locals()

        # we declare a special __extra_fields__ local var: this way, if we assign
        # __extra_fields__ inside a ClassDef, it will be automatically typechecked
        w_str_type_dict = self.vm.getitem_w(SPY.w_interp_dict, B.w_str, B.w_type)
        assert isinstance(w_str_type_dict, W_Type)
        self.declare_local("__extra_fields__", "red", w_str_type_dict, Loc.fake())

        for stmt in self.classdef.body:
            self.exec_stmt(stmt)

        body = ClassBody(self.classdef.loc, fields_w={}, dict_w={})
        for name, lv in self.locals.items():
            # ignore reserved bool locals
            if name.startswith("@"):
                continue
            if name == "__extra_fields__":
                if lv.w_val is not None:
                    body.dict_w["__extra_fields__"] = lv.w_val
                continue
            if lv.w_val is None:
                # locals declared but not assigned
                body.fields_w[name] = W_Field(name, lv.w_T, lv.decl_loc)
            else:
                body.dict_w[name] = lv.w_val

        return body

    def exec_stmt(self, stmt: ast.Stmt) -> None:
        allowed = (
            ast.VarDef,
            ast.Assign,
            ast.AssignLocal,
            ast.If,
            ast.Pass,
            ast.FuncDef,
        )
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
