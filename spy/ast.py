import astpretty
import pprint
import ast as py_ast
import dataclasses
from dataclasses import dataclass


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
