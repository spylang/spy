from dataclasses import dataclass

class Node:
    pass

@dataclass
class Stmt(Node):
    pass

@dataclass
class Expr(Node):
    pass

@dataclass
class Module:
    body: list[Stmt]

@dataclass
class Assign(Stmt):
    target: str
    value: Expr

@dataclass
class If(Stmt):
    test: Expr
    then_body: list[Stmt]
    else_body: list[Stmt]

@dataclass
class Const(Expr)
    value: int

@dataclass
class BinOp(Expr):
    op: str
    left: Expr
    right: Expr
