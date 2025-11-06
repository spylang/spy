import ast as py_ast
import dataclasses
import typing
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Iterator,
    Optional,
    Type,
    dataclass_transform,
    no_type_check,
)

from spy.analyze.symtable import Color, ImportRef, Symbol, VarKind
from spy.fqn import FQN
from spy.location import Loc
from spy.util import extend

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

AnyNode = typing.Union[py_ast.AST, "Node"]
ClassKind = typing.Literal["class", "struct", "typelift"]
FuncKind = typing.Literal["plain", "generic", "metafunc"]


@extend(py_ast.AST)
class AST:
    """
    monkey patch py_ast.AST to add a loc property. See also the comments in
    stubs/_ast.pyi
    """

    _loc: None = None

    @property
    def loc(self) -> Loc:
        if self._loc is not None:
            return self._loc
        raise ValueError(f"{self.__class__.__name__} does not have a location")

    @no_type_check
    def compute_all_locs(self, filename: str) -> None:
        """
        Compute .loc for itself and all its descendants.
        """
        for py_node in py_ast.walk(self):  # type: ignore
            if hasattr(py_node, "lineno"):
                assert py_node.end_lineno is not None
                assert py_node.end_col_offset is not None
                loc = Loc(
                    filename=filename,
                    line_start=py_node.lineno,
                    line_end=py_node.end_lineno,
                    col_start=py_node.col_offset,
                    col_end=py_node.end_col_offset,
                )
                py_node._loc = loc

    @typing.no_type_check
    def pp(self, *, hl=None) -> None:
        import spy.ast_dump

        spy.ast_dump.pprint(self, hl=hl)


del AST


@dataclass_transform(field_specifiers=(dataclasses.field,))
def AstNode[T](klass: Type[T]) -> Type[T]:
    """Decorator to create dataclasses for AST nodes
    We want all nodes to compare by *identity* and be hashable, because e.g. we
    put them in dictionaries inside the typechecker."""
    return dataclass(eq=False)(klass)


@AstNode
class Node:
    loc: Loc = field(repr=False)

    def pp(self, hl: Any = None, vm: Optional["SPyVM"] = None) -> None:
        import spy.ast_dump

        spy.ast_dump.pprint(self, hl=hl, vm=vm)

    @typing.no_type_check
    def ppc(self) -> None:
        """
        Like .pp(), but also copies the output in the clipboard. Useful for
        copy&paste expected output into your editor.
        """
        import spy.ast_dump

        spy.ast_dump.pprint(self, copy_to_clipboard=True)

    def replace(self, **kwargs: Any) -> Any:
        return dataclasses.replace(self, **kwargs)

    def walk(self, cls: Optional[type] = None) -> Iterator["Node"]:
        if cls is None or isinstance(self, cls):
            yield self
        for node in self.get_children():
            yield from node.walk(cls)

    def get_children(self) -> Iterator["Node"]:
        for f in self.__dataclass_fields__.values():
            value = getattr(self, f.name)
            if isinstance(value, Node):
                yield value
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, Node):
                        yield item

    def visit(self, prefix: str, visitor: Any, *args: Any) -> None:
        """
        Generic visitor algorithm.

        For each node of class Foo, we try to locate and call a method called
        {prefix}_Foo on the visitor object:

          - if it exists, it is called. It is responsibility of the method to
            visit its children, if wanted

          - if it doesn't exist, we recurively visit its children
        """
        cls = self.__class__.__name__
        methname = f"{prefix}_{cls}"
        meth = getattr(visitor, methname, None)
        if meth:
            meth(self, *args)
        else:
            for node in self.get_children():
                node.visit(prefix, visitor, *args)


@AstNode
class Module(Node):
    filename: str
    docstring: Optional[str]
    decls: list["Decl"]

    def get_funcdef(self, name: str) -> "FuncDef":
        """
        Search for the FuncDef with the given name.
        """
        for decl in self.decls:
            if isinstance(decl, GlobalFuncDef) and decl.funcdef.name == name:
                return decl.funcdef
        raise KeyError(name)

    def get_classdef(self, name: str) -> "ClassDef":
        """
        Search for the ClassDef with the given name.
        """
        for decl in self.decls:
            if isinstance(decl, GlobalClassDef) and decl.classdef.name == name:
                return decl.classdef
        raise KeyError(name)


class Decl(Node):
    pass


@AstNode
class GlobalFuncDef(Decl):
    funcdef: "FuncDef"


@AstNode
class GlobalVarDef(Decl):
    vardef: "VarDef"


@AstNode
class GlobalClassDef(Decl):
    classdef: "ClassDef"


@AstNode
class Import(Decl):
    loc_asname: Loc
    ref: ImportRef
    asname: str


# ====== Expr hierarchy ======


@AstNode
class Expr(Node):
    """
    Operator precedence table, see
    https://docs.python.org/3/reference/expressions.html#operator-precedence

    PREC  OPERATOR
    17    (expr...),  [expr...], {key: value...}, {expr...}
    16    x[index], x[index:index], x(arguments...), x.attribute
    15    await x
    14    **
    13    +x, -x, ~x
    12    *, @, /, //, %
    11    +, -
    10    <<, >>
     9    &
     8    ^
     7    |
     6    in, not in, is, is not, <, <=, >, >=, !=, ==
     5    not x
     4    and
     3    or
     2    if – else
     1    lambda
     0    :=
    """

    # precedence must be overriden by subclasses. The weird type comment is
    # needed to make mypy happy
    precedence = "<Expr.precedence not set>"  # type: int # type: ignore


@AstNode
class Name(Expr):
    precedence = 100  # the highest
    id: str


@AstNode
class Auto(Expr):
    precedence = 100  # the highest


@AstNode
class Constant(Expr):
    precedence = 100  # the highest
    value: object

    def __post_init__(self) -> None:
        assert type(self.value) is not str, "use StrConst instead"


@AstNode
class StrConst(Expr):
    """
    Like Constant, but for strings.

    The reason we have a specialized node is that we want to use it for fields
    than MUST be strings, like GetAttr.attr or Assign.target.
    """

    precedence = 100  # the highest
    value: str


@AstNode
class LocConst(Expr):
    """
    Like Constant, but for W_Locs.

    The reason for this is that we treat W_Locs as value types and we don't
    want to give them an FQN just for redshifting.
    """

    precedence = 100  # the highest
    value: Loc


@AstNode
class GetItem(Expr):
    precedence = 16
    value: Expr
    args: list[Expr]


@AstNode
class List(Expr):
    precedence = 17
    items: list[Expr]


@AstNode
class Tuple(Expr):
    precedence = 17
    items: list[Expr]


@AstNode
class Call(Expr):
    precedence = 16
    func: Expr
    args: list[Expr]


@AstNode
class CallMethod(Expr):
    precedence = 17  # higher than GetAttr
    target: Expr
    method: StrConst
    args: list[Expr]


@AstNode
class GetAttr(Expr):
    precedence = 16
    value: Expr
    attr: StrConst


@AstNode
class BinOp(Expr):
    op: str
    left: Expr
    right: Expr
    # fmt: off
    _precendece = {
        "|":   7,
        "^":   8,
        "&":   9,
        "<<": 10,
        ">>": 10,
        "+":  11,
        "-":  11,
        "*":  12,
        "/":  12,
        "//": 12,
        "%":  12,
        "@":  12,
        "**": 14,
    }
    # fmt: on

    @property
    def precedence(self) -> int:
        return self._precendece[self.op]

    # this is just to make mypy happy
    @precedence.setter
    def precedence(self, newval: int) -> None:
        raise TypeError("readonly attribute")


# eventually this should allow chained comparisons, but for now we support
# only binary ones
@AstNode
class CmpOp(Expr):
    op: str
    left: Expr
    right: Expr
    # fmt: off
    _precendece = {
        "==":  6,
        "!=":  6,
        "<":   6,
        "<=":  6,
        ">":   6,
        ">=":  6,
        "is":  6,
        "in":  6,
        "is not": 6,
        "not in": 6,
    }
    # fmt: on

    @property
    def precedence(self) -> int:
        return self._precendece[self.op]

    # this is just to make mypy happy
    @precedence.setter
    def precedence(self, newval: int) -> None:
        raise TypeError("readonly attribute")


@AstNode
class UnaryOp(Expr):
    op: str
    value: Expr
    # fmt: off
    _precendece = {
        "not": 5,
        "+":  13,
        "-":  13,
        "~":  13,
    }
    # fmt: on

    @property
    def precedence(self) -> int:
        return self._precendece[self.op]

    # this is just to make mypy happy
    @precedence.setter
    def precedence(self, newval: int) -> None:
        raise TypeError("readonly attribute")


# ====== Stmt hierarchy ======


@AstNode
class Stmt(Node):
    pass


@AstNode
class FuncArg(Node):
    name: str
    type: "Expr"


@AstNode
class FuncDef(Stmt):
    color: Color
    kind: FuncKind
    name: str
    args: list[FuncArg]
    vararg: Optional[FuncArg]
    return_type: "Expr"
    docstring: Optional[str]
    body: list["Stmt"]
    decorators: list["Expr"]
    symtable: Any = field(repr=False, default=None)

    @property
    def prototype_loc(self) -> Loc:
        """
        Return the Loc which corresponds to the func prototype, i.e. from the
        'def' until the return type.
        """
        return Loc.combine(self.loc, self.return_type.loc)


@AstNode
class ClassDef(Stmt):
    body_loc: Loc
    name: str
    kind: ClassKind
    docstring: Optional[str]
    fields: list["VarDef"]
    body: list["Stmt"]
    symtable: Any = field(repr=False, default=None)


@AstNode
class Pass(Stmt):
    pass


@AstNode
class Return(Stmt):
    value: Expr


@AstNode
class VarDef(Stmt):
    kind: Optional[VarKind]
    name: StrConst
    type: Expr
    value: Optional[Expr]


@AstNode
class StmtExpr(Stmt):
    """
    An expr used as a statement
    """

    value: Expr


@AstNode
class Assign(Stmt):
    target: StrConst
    value: Expr


@AstNode
class UnpackAssign(Stmt):
    targets: list[StrConst]
    value: Expr


@AstNode
class AugAssign(Stmt):
    op: str
    target: StrConst
    value: Expr


@AstNode
class SetAttr(Stmt):
    target: Expr
    attr: StrConst
    value: Expr


@AstNode
class SetItem(Stmt):
    target: Expr
    args: list[Expr]
    value: Expr


@AstNode
class If(Stmt):
    test: Expr
    then_body: list[Stmt]
    else_body: list[Stmt]

    @property
    def has_else(self) -> bool:
        return len(self.else_body) > 0


@AstNode
class While(Stmt):
    test: Expr
    body: list[Stmt]


@AstNode
class For(Stmt):
    seq: int  # unique id within a funcdef
    target: StrConst
    iter: Expr
    body: list[Stmt]


@AstNode
class Raise(Stmt):
    exc: Expr


@AstNode
class Assert(Stmt):
    test: Expr
    msg: Optional[Expr]


@AstNode
class Break(Stmt):
    pass


@AstNode
class Continue(Stmt):
    pass


# ====== IR-specific nodes ======
#
# The following nodes are special: they are never generated by the parser, but
# only by the ASTFrame and/or Doppler. In other words, they are not part of
# the proper AST-which-represent-the-syntax-of-the-language, but they are part
# of the AST-which-we-use-as-IR


@AstNode
class FQNConst(Expr):
    precedence = 100  # the highest
    fqn: FQN


# specialized Name nodes
@AstNode
class NameLocal(Expr):
    precedence = 100  # the highest
    sym: Symbol


@AstNode
class NameOuterDirect(Expr):
    precedence = 100  # the highest
    sym: Symbol


@AstNode
class NameOuterCell(Expr):
    precedence = 100  # the highest
    sym: Symbol
    fqn: FQN


@AstNode
class AssignLocal(Stmt):
    target: StrConst
    value: Expr


@AstNode
class AssignCell(Stmt):
    target: StrConst
    target_fqn: FQN
    value: Expr
