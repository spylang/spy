"""
Example code for how to use spyast.js.

THIS FILE IS NOT A FUNCTIONAL PART OF SPy
"""

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


@dataclass
class Name(Expr):
    name: str


@dataclass
class UnaryOp(Expr):
    op: str
    operand: Expr


@dataclass
class FuncArg(Node):
    name: str
    type: Expr


@dataclass
class Return(Stmt):
    value: Expr


@dataclass
class FuncDef(Stmt):
    name: str
    args: list[FuncArg]
    return_type: Expr
    body: list[Stmt]


def attach_src(node):
    if isinstance(node, Const):
        node.src = str(node.value)
    elif isinstance(node, Name):
        node.src = node.name
    elif isinstance(node, FuncArg):
        attach_src(node.type)
        node.src = f"{node.name}: {node.type.src}"
    elif isinstance(node, Return):
        attach_src(node.value)
        node.src = f"return {node.value.src}"
    elif isinstance(node, FuncDef):
        for arg in node.args:
            attach_src(arg)
        attach_src(node.return_type)
        for s in node.body:
            attach_src(s)
        args_src = ", ".join(a.src for a in node.args)
        body_lines = "\n".join(f"    {s.src}" for s in node.body)
        node.src = (
            f"def {node.name}({args_src}) -> {node.return_type.src}:\n{body_lines}"
        )
    elif isinstance(node, UnaryOp):
        attach_src(node.operand)
        node.src = f"{node.op}{node.operand.src}"
    elif isinstance(node, BinOp):
        attach_src(node.left)
        attach_src(node.right)
        node.src = f"{node.left.src} {node.op} {node.right.src}"
    elif isinstance(node, Assign):
        attach_src(node.value)
        node.src = f"{node.target} = {node.value.src}"
    elif isinstance(node, If):
        attach_src(node.test)
        for s in node.then_body:
            attach_src(s)
        for s in node.else_body:
            attach_src(s)
        then_lines = "\n".join(f"    {s.src}" for s in node.then_body)
        else_lines = "\n".join(f"    {s.src}" for s in node.else_body)
        node.src = f"if {node.test.src}:\n{then_lines}\nelse:\n{else_lines}"
    elif isinstance(node, Module):
        for s in node.body:
            attach_src(s)
        node.src = "\n".join(s.src for s in node.body)


# x = 1 + 2 * 3
# if (1 + 4) > 3:
#     y = x + 1
# else:
#     y = 0
# def add(a: int, b: int) -> int:
#     result = a + b
EXAMPLE = Module(
    body=[
        Assign(
            target="x",
            value=BinOp("+", Const(1), BinOp("*", Const(2), Const(3))),
        ),
        Assign(
            target="neg",
            value=UnaryOp("-", Name("x")),
        ),
        If(
            test=BinOp(">", BinOp("+", Const(1), Const(4)), Const(3)),
            then_body=[
                Assign(target="y", value=BinOp("+", Const(0), Const(1))),
            ],
            else_body=[
                Assign(target="y", value=Const(0)),
            ],
        ),
        FuncDef(
            name="add",
            args=[
                FuncArg(name="a", type=Name("int")),
                FuncArg(name="b", type=Name("int")),
            ],
            return_type=Name("int"),
            body=[
                Assign(target="result", value=BinOp("+", Name("a"), Name("b"))),
                Return(value=Name("result")),
            ],
        ),
    ]
)
attach_src(EXAMPLE)
