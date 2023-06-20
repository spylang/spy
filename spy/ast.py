import typing
import astpretty
import pprint
import ast as py_ast
from dataclasses import dataclass
from spy.location import Loc
from spy.util import extend

AnyNode = typing.Union[py_ast.AST, 'Node']

@extend(py_ast.AST)
class AST:
    """
    monkey patch py_ast.AST to add a get_loc method. See also the comments in
    stubs/_ast.pyi
    """

    @typing.no_type_check
    def get_loc(self) -> Loc:
        if isinstance(self, py_ast.Module):
            raise TypeError('py_ast.Module does not have a location')
        #
        # all the other nodes should have a location. If they don't, we should
        # investigate and decide what to do
        assert hasattr(self, 'lineno')
        assert self.end_lineno is not None
        assert self.end_col_offset is not None
        return Loc(
            line_start = self.lineno,
            line_end = self.end_lineno,
            col_start = self.col_offset,
            col_end = self.end_col_offset,
        )

    @typing.no_type_check
    def pp(self) -> None:
        import spy.ast_dump
        spy.ast_dump.pprint(self)

del AST


@dataclass
class Node:

    def get_loc(self) -> Loc:
        if hasattr(self, 'loc'):
            return self.loc
        raise TypeError(f'{self.__class__.__name__} does not have a location')

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
    type: py_ast.expr


@dataclass(eq=False)
class FuncDef(Decl):
    loc: Loc
    name: str
    args: list[FuncArg]
    return_type: py_ast.expr
    body: list[py_ast.stmt]

    def __hash__(self) -> int:
        return id(self)
