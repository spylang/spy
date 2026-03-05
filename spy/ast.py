# ================== IMPORTANT: .spyc versioning =================
# Update importing.SPYC_VERSION in case of any significant change
# ================================================================

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
    from spy.vm.object import W_Type
    from spy.vm.vm import SPyVM

ClassKind = typing.Literal["class", "struct"]
FuncKind = typing.Literal["plain", "generic", "metafunc"]
FuncParamKind = typing.Literal["simple", "var_positional"]

# ==== Typed vs untyped ASTs ====
#
# The Expr class has an optional field w_T which indicates the type of the expression.
#
# AST trees are said UNTYPED when all their Exprs have w_T == None.
# AST trees are said TYPED when all their Exprs have w_T != None.
#
# It is a logical error to have AST trees which mix typed and untyped nodes.
#
# The parser produces UNTYPED ASTs. DopplerFrame produces TYPED ASTs.
# ================================


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


@dataclass_transform(field_specifiers=(dataclasses.field,), eq_default=False)
def astnode[T](klass: Type[T]) -> Type[T]:
    """Decorator to create dataclasses for AST nodes
    We want all nodes to compare by *identity* and be hashable, because e.g. we
    put them in dictionaries inside the typechecker."""
    return dataclass(eq=False)(klass)


@astnode
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


@astnode
class Module(Node):
    filename: str
    docstring: Optional[str]
    decls: list["Decl"]
    symtable: Any = field(repr=False, default=None)

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


@astnode
class GlobalFuncDef(Decl):
    funcdef: "FuncDef"


@astnode
class GlobalVarDef(Decl):
    vardef: "VarDef"


@astnode
class GlobalClassDef(Decl):
    classdef: "ClassDef"


@astnode
class Import(Decl):
    loc_asname: Loc
    ref: ImportRef
    asname: str


# ====== Expr hierarchy ======


@astnode
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

    # the type of the expression: present only in TYPED ASTs.
    w_T: Optional["W_Type"] = field(default=None, kw_only=True)


@astnode
class Name(Expr):
    precedence = 100  # the highest
    id: str


@astnode
class Auto(Expr):
    precedence = 100  # the highest


@astnode
class Constant(Expr):
    precedence = 100  # the highest
    value: object

    def __post_init__(self) -> None:
        assert type(self.value) is not str, "use StrConst instead"


@astnode
class StrConst(Expr):
    """
    Like Constant, but for strings.

    The reason we have a specialized node is that we want to use it for fields
    than MUST be strings, like GetAttr.attr or Assign.target.
    """

    precedence = 100  # the highest
    value: str


@astnode
class LocConst(Expr):
    """
    Like Constant, but for W_Locs.

    The reason for this is that we treat W_Locs as value types and we don't
    want to give them an FQN just for redshifting.
    """

    precedence = 100  # the highest
    value: Loc


@astnode
class GetItem(Expr):
    precedence = 16
    value: Expr
    args: list[Expr]


@astnode
class List(Expr):
    precedence = 17
    items: list[Expr]


@astnode
class Tuple(Expr):
    precedence = 17
    items: list[Expr]


@astnode
class KeyValuePair(Node):
    key: Expr
    value: Expr


@astnode
class Dict(Expr):
    precedence = 17
    items: list[KeyValuePair]


@astnode
class Call(Expr):
    precedence = 16
    func: Expr
    args: list[Expr]


@astnode
class Slice(Expr):
    precedence = 16
    start: Expr
    stop: Expr
    step: Expr


@astnode
class CallMethod(Expr):
    precedence = 17  # higher than GetAttr
    target: Expr
    method: StrConst
    args: list[Expr]


@astnode
class GetAttr(Expr):
    precedence = 16
    value: Expr
    attr: StrConst


@astnode
class BinOp(Expr):
    op: str
    left: Expr
    right: Expr
    # fmt: off
    _precedence = {
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
        return self._precedence[self.op]

    # this is just to make mypy happy
    @precedence.setter
    def precedence(self, newval: int) -> None:
        raise TypeError("readonly attribute")


# eventually this should allow chained comparisons, but for now we support
# only binary ones
@astnode
class CmpOp(Expr):
    op: str
    left: Expr
    right: Expr
    # fmt: off
    _precedence = {
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
        return self._precedence[self.op]

    # this is just to make mypy happy
    @precedence.setter
    def precedence(self, newval: int) -> None:
        raise TypeError("readonly attribute")


@astnode
class And(Expr):
    precedence = 4
    left: Expr
    right: Expr


@astnode
class Or(Expr):
    precedence = 3
    left: Expr
    right: Expr


@astnode
class UnaryOp(Expr):
    op: str
    value: Expr
    # fmt: off
    _precedence = {
        "not": 5,
        "+":  13,
        "-":  13,
        "~":  13,
    }
    # fmt: on

    @property
    def precedence(self) -> int:
        return self._precedence[self.op]

    # this is just to make mypy happy
    @precedence.setter
    def precedence(self, newval: int) -> None:
        raise TypeError("readonly attribute")


@astnode
class AssignExpr(Expr):
    precedence = 0
    target: StrConst
    value: Expr


# ====== Stmt hierarchy ======


@astnode
class Stmt(Node):
    pass


@astnode
class FuncArg(Node):
    name: str
    type: "Expr"
    kind: FuncParamKind


@astnode
class FuncDef(Stmt):
    color: Color
    kind: FuncKind
    name: str
    args: list[FuncArg]
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


@astnode
class ClassDef(Stmt):
    body_loc: Loc
    name: str
    kind: ClassKind
    docstring: Optional[str]
    body: list["Stmt"]
    symtable: Any = field(repr=False, default=None)


@astnode
class Pass(Stmt):
    pass


@astnode
class Return(Stmt):
    value: Expr


@astnode
class VarDef(Stmt):
    kind: Optional[VarKind]
    name: StrConst
    type: Expr
    value: Optional[Expr]


@astnode
class StmtExpr(Stmt):
    """
    An expr used as a statement
    """

    value: Expr


@astnode
class Assign(Stmt):
    target: StrConst
    value: Expr


@astnode
class UnpackAssign(Stmt):
    targets: list[StrConst]
    value: Expr


@astnode
class AugAssign(Stmt):
    op: str
    target: StrConst
    value: Expr


@astnode
class SetAttr(Stmt):
    target: Expr
    attr: StrConst
    value: Expr


@astnode
class SetItem(Stmt):
    target: Expr
    args: list[Expr]
    value: Expr


@astnode
class If(Stmt):
    test: Expr
    then_body: list[Stmt]
    else_body: list[Stmt]

    @property
    def has_else(self) -> bool:
        return len(self.else_body) > 0


@astnode
class While(Stmt):
    test: Expr
    body: list[Stmt]


@astnode
class For(Stmt):
    seq: int  # unique id within a funcdef
    target: StrConst
    iter: Expr
    body: list[Stmt]


@astnode
class Raise(Stmt):
    exc: Expr


@astnode
class Assert(Stmt):
    test: Expr
    msg: Optional[Expr]


@astnode
class Break(Stmt):
    pass


@astnode
class Continue(Stmt):
    pass


# ====== IR-specific nodes ======
#
# The following nodes are special: they are never generated by the parser, but
# only by the ASTFrame and/or Doppler. In other words, they are not part of
# the proper AST-which-represent-the-syntax-of-the-language, but they are part
# of the AST-which-we-use-as-IR


@astnode
class FQNConst(Expr):
    precedence = 100  # the highest
    fqn: FQN


# specialized Name nodes
@astnode
class NameImportRef(Expr):
    precedence = 100  # the highest
    sym: Symbol


@astnode
class NameLocalDirect(Expr):
    precedence = 100  # the highest
    sym: Symbol


@astnode
class NameLocalCell(Expr):
    precedence = 100  # the highest
    sym: Symbol


@astnode
class NameOuterDirect(Expr):
    precedence = 100  # the highest
    sym: Symbol


@astnode
class NameOuterCell(Expr):
    precedence = 100  # the highest
    sym: Symbol
    fqn: FQN


@astnode
class AssignLocal(Stmt):
    target: StrConst
    value: Expr


@astnode
class AssignCell(Stmt):
    target: StrConst
    target_fqn: FQN
    value: Expr


@astnode
class AssignExprLocal(Expr):
    precedence = 0
    target: StrConst
    value: Expr


@astnode
class AssignExprCell(Expr):
    precedence = 0
    target: StrConst
    target_fqn: FQN
    value: Expr
