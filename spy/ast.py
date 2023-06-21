import typing
import pprint
import ast as py_ast
from dataclasses import dataclass
from spy.location import Loc
from spy.util import extend

AnyNode = typing.Union[py_ast.AST, 'Node']

@extend(py_ast.AST)
class AST:
    """
    monkey patch py_ast.AST to add a loc property. See also the comments in
    stubs/_ast.pyi
    """

    _loc = None

    @property
    def loc(self) -> Loc:
        if self._loc is not None:
            return self._loc
        raise ValueError(f'{self.__class__.__name__} does not have a location')

    def compute_all_locs(self, filename: str) -> None:
        """
        Compute .loc for itself and all its descendants.
        """
        for py_node in py_ast.walk(self):  # type: ignore
            if hasattr(py_node, 'lineno'):
                assert py_node.end_lineno is not None
                assert py_node.end_col_offset is not None
                loc = Loc(
                    filename = filename,
                    line_start = py_node.lineno,
                    line_end = py_node.end_lineno,
                    col_start = py_node.col_offset,
                    col_end = py_node.end_col_offset,
                )
                py_node._loc = loc

    @typing.no_type_check
    def pp(self) -> None:
        import spy.ast_dump
        spy.ast_dump.pprint(self)

del AST


@dataclass
class Node:

    def pp(self) -> None:
        import spy.ast_dump
        spy.ast_dump.pprint(self)


@dataclass
class Module(Node):
    filename: str
    decls: list['Decl']


class Decl(Node):
    pass


@dataclass
class FuncArg(Node):
    loc: Loc
    name: str
    type: 'Expr'


@dataclass(eq=False)
class FuncDef(Decl):
    loc: Loc
    name: str
    args: list[FuncArg]
    return_type: 'Expr'
    body: list['Stmt']

    def __hash__(self) -> int:
        return id(self)


# ====== Expr hierarchy ======

@dataclass
class Expr(Node):
    loc: Loc

@dataclass
class Name(Expr):
    id: str

@dataclass(eq=False)
class Constant(Expr):
    value: object

    def __hash__(self) -> int:
        return id(self)


# ====== Stmt hierarchy ======

@dataclass
class Stmt(Node):
    loc: Loc

@dataclass
class Pass(Stmt):
    pass

@dataclass
class Return(Stmt):
    value: Expr
