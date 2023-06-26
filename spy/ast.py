import typing
from typing import Optional, Literal
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


# we want all nodes to compare by *identity* and be hashable, because e.g. we
# put them in dictionaries inside the typechecker. So, we must use eq=False ON
# ALL AST NODES.
#
# Ideally, I would like to do the following:
#     def astnode():
#         return dataclass (eq=False)
#
#     @astnode
#     class Node:
#         ...
#
# But we can't because this pattern is not understood by mypy.

@dataclass(eq=False)
class Node:

    def pp(self) -> None:
        import spy.ast_dump
        spy.ast_dump.pprint(self)

    @typing.no_type_check
    def ppc(self) -> None:
        """
        Like .pp(), but also copies the output in the clipboard. Useful for
        copy&paste expected output into your editor.
        """
        import spy.ast_dump
        spy.ast_dump.pprint(self, copy_to_clipboard=True)


@dataclass(eq=False)
class Module(Node):
    filename: str
    decls: list['Decl']


class Decl(Node):
    pass


@dataclass(eq=False)
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


@dataclass(eq=False)
class GlobalVarDef(Decl):
    vardef: 'VarDef'

    @property
    def loc(self) -> Loc:
        return self.vardef.loc

# ====== Expr hierarchy ======

@dataclass(eq=False)
class Expr(Node):
    loc: Loc

@dataclass(eq=False)
class Name(Expr):
    id: str


@dataclass(eq=False)
class Constant(Expr):
    value: object

@dataclass(eq=False)
class GetItem(Expr):
    value: Expr
    index: Expr

@dataclass(eq=False)
class List(Expr):
    items: list[Expr]

@dataclass(eq=False)
class Call(Expr):
    func: Expr
    args: list[Expr]

# ====== BinOp sub-hierarchy ======

@dataclass(eq=False)
class BinOp(Expr):
    op = ''
    left: Expr
    right: Expr

@dataclass(eq=False)
class Add(BinOp):
    op = '+'

@dataclass(eq=False)
class Sub(BinOp):
    op = '-'

@dataclass(eq=False)
class Mul(BinOp):
    op = '*'

@dataclass(eq=False)
class Div(BinOp):
    op = '/'

@dataclass(eq=False)
class FloorDiv(BinOp):
    op = '//'

@dataclass(eq=False)
class Mod(BinOp):
    op = '%'

@dataclass(eq=False)
class Pow(BinOp):
    op = '**'

@dataclass(eq=False)
class LShift(BinOp):
    op = '<<'

@dataclass(eq=False)
class RShift(BinOp):
    op = '>>'

@dataclass(eq=False)
class BitXor(BinOp):
    op = '^'

@dataclass(eq=False)
class BitOr(BinOp):
    op = '|'

@dataclass(eq=False)
class BitAnd(BinOp):
    op = '&'

@dataclass(eq=False)
class MatMul(BinOp):
    op = '@'


# ====== Stmt hierarchy ======

@dataclass(eq=False)
class Stmt(Node):
    loc: Loc

@dataclass(eq=False)
class Pass(Stmt):
    pass

@dataclass(eq=False)
class Return(Stmt):
    value: Expr

@dataclass(eq=False)
class VarDef(Stmt):
    name: str
    type: Expr
    value: Optional[Expr]

@dataclass(eq=False)
class Assign(Stmt):
    target_loc: Loc
    target: str
    value: Expr
