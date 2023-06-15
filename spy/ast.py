import ast as py_ast
from dataclasses import dataclass

@dataclass
class Location:
    line_start: int
    line_end: int
    col_start: int
    col_end: int


@dataclass
class Node:
    loc: Location


@dataclass
class Module(Node):
    decls: list['Decl']


class Decl(Node):
    pass


@dataclass
class FuncArgs:
    pass


@dataclass
class FuncDef(Decl):
    name: str
    args: FuncArgs
    return_type: 'Name'


@dataclass
class Expr(Node):
    pass


@dataclass
class Name(Expr):
    id: str
