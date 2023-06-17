import astpretty
import pprint
import ast as py_ast
import dataclasses
from dataclasses import dataclass

# monkey-patch python's AST to add a pp() method
py_ast.AST.pp = astpretty.pprint  # type:ignore


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
        from spy.ast_dump import dump
        print(dump(self))


@dataclass
class Module(Node):
    decls: list['Decl']


class Decl(Node):
    pass


@dataclass
class FuncArg(Node):
    loc: Location
    name: str
    type: 'Name'

@dataclass
class FuncDef(Decl):
    loc: Location
    name: str
    args: list[FuncArg]
    return_type: 'Name'
    body: list[py_ast.stmt]


@dataclass
class Expr(Node):
    loc: Location


@dataclass
class Name(Expr):
    loc: Location
    id: str
