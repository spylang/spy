import astpretty
import pprint
import ast as py_ast
import dataclasses
from dataclasses import dataclass

def get_loc(py_node: py_ast.AST) -> 'Location':
    if isinstance(py_node, py_ast.Module):
        raise TypeError('py_ast.Module does not have a location')
    #
    # all the other nodes should have a location. If they don't, we should
    # investigate and decide what to do
    assert hasattr(py_node, 'lineno')
    assert py_node.end_lineno is not None
    assert py_node.end_col_offset is not None
    return Location(
        line_start = py_node.lineno,
        line_end = py_node.end_lineno,
        col_start = py_node.col_offset,
        col_end = py_node.end_col_offset,
    )


@dataclass
class Location:
    line_start: int
    line_end: int
    col_start: int
    col_end: int

    def replace(self, **kwargs: int) -> 'Location':
        return dataclasses.replace(self, **kwargs)


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
    loc: Location
    name: str
    type: py_ast.expr

@dataclass
class FuncDef(Decl):
    loc: Location
    name: str
    args: list[FuncArg]
    return_type: py_ast.expr
    body: list[py_ast.stmt]
