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
class Const(Expr):
    value: int

@dataclass
class BinOp(Expr):
    op: str
    left: Expr
    right: Expr


# x = 1 + 2 * 3
# if (1 + 4) > 3:
#     y = x + 1
# else:
#     y = 0
EXAMPLE = Module(body=[
    Assign(
        target='x',
        value=BinOp('+', Const(1), BinOp('*', Const(2), Const(3))),
    ),
    If(
        test=BinOp('>', BinOp('+', Const(1), Const(4)), Const(3)),
        then_body=[
            Assign(target='y', value=BinOp('+', Const(0), Const(1))),
        ],
        else_body=[
            Assign(target='y', value=Const(0)),
        ],
    ),
])
