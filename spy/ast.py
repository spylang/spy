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
    loc: Location


@dataclass
class Module:
    decls: list['Decl']


class Decl(Node):
    pass


@dataclass
class FuncArg(Node):
    name: str
    type: 'Name'

@dataclass
class FuncDef(Decl):
    name: str
    args: list[FuncArg]
    return_type: 'Name'
    body: list[py_ast.stmt]


@dataclass
class Expr(Node):
    pass


@dataclass
class Name(Expr):
    id: str
