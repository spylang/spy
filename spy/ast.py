import typing
from typing import Optional, Iterator, Any, no_type_check
import ast as py_ast
import dataclasses
from dataclasses import dataclass, field
from spy.fqn import FQN
from spy.location import Loc
from spy.analyze.symtable import Color
from spy.util import extend

AnyNode = typing.Union[py_ast.AST, 'Node']
VarKind = typing.Literal['const', 'var']
ClassKind = typing.Literal['class', 'struct', 'typelift']
FuncKind = typing.Literal['plain', 'generic', 'metafunc']

@extend(py_ast.AST)
class AST:
    """
    monkey patch py_ast.AST to add a loc property. See also the comments in
    stubs/_ast.pyi
    """

    _loc = None

    @property
    def loc(self) -> Loc:
        if self._loc is not None:
            return self._loc
        raise ValueError(f'{self.__class__.__name__} does not have a location')

    @no_type_check
    def compute_all_locs(self, filename: str) -> None:
        """
        Compute .loc for itself and all its descendants.
        """
        for py_node in py_ast.walk(self):  # type: ignore
            if hasattr(py_node, 'lineno'):
                assert py_node.end_lineno is not None
                assert py_node.end_col_offset is not None
                loc = Loc(
                    filename = filename,
                    line_start = py_node.lineno,
                    line_end = py_node.end_lineno,
                    col_start = py_node.col_offset,
                    col_end = py_node.end_col_offset,
                )
                py_node._loc = loc

    @typing.no_type_check
    def pp(self, *, hl=None) -> None:
        import spy.ast_dump
        spy.ast_dump.pprint(self, hl=hl)

del AST

# we want all nodes to compare by *identity* and be hashable, because e.g. we
# put them in dictionaries inside the typechecker. So, we must use eq=False ON
# ALL AST NODES.
#
# Ideally, I would like to do the following:
#     def astnode():
#         return dataclass (eq=False)
#
#     @astnode
#     class Node:
#         ...
#
# But we can't because this pattern is not understood by mypy.

@dataclass(eq=False)
class Node:
    loc: Loc = field(repr=False)

    def pp(self, hl: Any=None, colorize: bool = False) -> None:
        import spy.ast_dump
        spy.ast_dump.pprint(self, hl=hl, colorize=colorize)

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

    def walk(self, cls: Optional[type] = None) -> Iterator['Node']:
        if cls is None or isinstance(self, cls):
            yield self
        for node in self.get_children():
            yield from node.walk(cls)

    def get_children(self) -> Iterator['Node']:
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
        methname = f'{prefix}_{cls}'
        meth = getattr(visitor, methname, None)
        if meth:
            meth(self, *args)
        else:
            for node in self.get_children():
                node.visit(prefix, visitor, *args)

@dataclass(eq=False)
class Module(Node):
    filename: str
    docstring: Optional[str]
    decls: list['Decl']

    def get_funcdef(self, name: str) -> 'FuncDef':
        """
        Search for the FuncDef with the given name.
        """
        for decl in self.decls:
            if isinstance(decl, GlobalFuncDef) and decl.funcdef.name == name:
                return decl.funcdef
        raise KeyError(name)

    def get_classdef(self, name: str) -> 'ClassDef':
        """
        Search for the ClassDef with the given name.
        """
        for decl in self.decls:
            if isinstance(decl, GlobalClassDef) and decl.classdef.name == name:
                return decl.classdef
        raise KeyError(name)


class Decl(Node):
    pass


@dataclass(eq=False)
class GlobalFuncDef(Decl):
    funcdef: 'FuncDef'


@dataclass(eq=False)
class GlobalVarDef(Decl):
    vardef: 'VarDef'
    assign: 'Assign'


@dataclass(eq=False)
class GlobalClassDef(Decl):
    classdef: 'ClassDef'


@dataclass(eq=False)
class Import(Decl):
    loc_asname: Loc
    fqn: FQN
    asname: str

# ====== Expr hierarchy ======

@dataclass(eq=False)
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
    precedence = '<Expr.precedence not set>' # type: int # type: ignore


@dataclass(eq=False)
class Name(Expr):
    precedence = 100 # the highest
    id: str

@dataclass(eq=False)
class Auto(Expr):
    precedence = 100 # the highest

@dataclass(eq=False)
class Constant(Expr):
    precedence = 100 # the highest
    value: object

    def __post_init__(self) -> None:
        assert type(self.value) is not str, 'use StrConst instead'

@dataclass(eq=False)
class StrConst(Expr):
    """
    Like Constant, but for strings.

    The reason we have a specialized node is that we want to use it for fields
    than MUST be strings, like GetAttr.attr or Assign.target.
    """
    precedence = 100 # the highest
    value: str

@dataclass(eq=False)
class GetItem(Expr):
    precedence = 16
    value: Expr
    args: list[Expr]

@dataclass(eq=False)
class List(Expr):
    precedence = 17
    items: list[Expr]

@dataclass(eq=False)
class Tuple(Expr):
    precedence = 17
    items: list[Expr]

@dataclass(eq=False)
class Call(Expr):
    precedence = 16
    func: Expr
    args: list[Expr]

@dataclass(eq=False)
class CallMethod(Expr):
    precedence = 17 # higher than GetAttr
    target: Expr
    method: StrConst
    args: list[Expr]

@dataclass(eq=False)
class GetAttr(Expr):
    precedence = 16
    value: Expr
    attr: StrConst


@dataclass(eq=False)
class BinOp(Expr):
    op: str
    left: Expr
    right: Expr

    _precendece = {
        '|':   7,
        '^':   8,
        '&':   9,
        '<<': 10,
        '>>': 10,
        '+':  11,
        '-':  11,
        '*':  12,
        '/':  12,
        '//': 12,
        '%':  12,
        '@':  12,
        '**': 14,
    }

    @property
    def precedence(self) -> int:
        return self._precendece[self.op]

    # this is just to make mypy happy
    @precedence.setter
    def precedence(self, newval: int) -> None:
        raise TypeError('readonly attribute')


# eventually this should allow chained comparisons, but for now we support
# only binary ones
@dataclass(eq=False)
class CmpOp(Expr):
    op: str
    left: Expr
    right: Expr

    _precendece = {
        '==':  6,
        '!=':  6,
        '<':   6,
        '<=':  6,
        '>':   6,
        '>=':  6,
        'is':  6,
        'in':  6,
        'is not': 6,
        'not in': 6,
    }

    @property
    def precedence(self) -> int:
        return self._precendece[self.op]

    # this is just to make mypy happy
    @precedence.setter
    def precedence(self, newval: int) -> None:
        raise TypeError('readonly attribute')


@dataclass(eq=False)
class UnaryOp(Expr):
    op: str
    value: Expr

    _precendece = {
        'not': 5,
        '+':  13,
        '-':  13,
        '~':  13,
    }

    @property
    def precedence(self) -> int:
        return self._precendece[self.op]

    # this is just to make mypy happy
    @precedence.setter
    def precedence(self, newval: int) -> None:
        raise TypeError('readonly attribute')



# ====== Stmt hierarchy ======

@dataclass(eq=False)
class Stmt(Node):
    pass

@dataclass(eq=False)
class FuncArg(Node):
    name: str
    type: 'Expr'

@dataclass(eq=False)
class FuncDef(Stmt):
    color: Color
    kind: FuncKind
    name: str
    args: list[FuncArg]
    return_type: 'Expr'
    docstring: Optional[str]
    body: list['Stmt']
    symtable: Any = field(repr=False, default=None)

    @property
    def prototype_loc(self) -> Loc:
        """
        Return the Loc which corresponds to the func prototype, i.e. from the
        'def' until the return type.
        """
        return Loc.combine(self.loc, self.return_type.loc)

@dataclass(eq=False)
class ClassDef(Stmt):
    name: str
    kind: ClassKind
    docstring: Optional[str]
    fields: list['VarDef']
    body: list['Stmt']
    symtable: Any = field(repr=False, default=None)

@dataclass(eq=False)
class Pass(Stmt):
    pass

@dataclass(eq=False)
class Return(Stmt):
    value: Expr

@dataclass(eq=False)
class VarDef(Stmt):
    kind: VarKind
    name: str
    type: Expr

@dataclass(eq=False)
class StmtExpr(Stmt):
    """
    An expr used as a statement
    """
    value: Expr

@dataclass(eq=False)
class Assign(Stmt):
    target: StrConst
    value: Expr

@dataclass(eq=False)
class UnpackAssign(Stmt):
    targets: list[StrConst]
    value: Expr

@dataclass(eq=False)
class AugAssign(Stmt):
    op: str
    target: StrConst
    value: Expr

@dataclass(eq=False)
class SetAttr(Stmt):
    target: Expr
    attr: StrConst
    value: Expr

@dataclass(eq=False)
class SetItem(Stmt):
    target: Expr
    args: list[Expr]
    value: Expr

@dataclass(eq=False)
class If(Stmt):
    test: Expr
    then_body: list[Stmt]
    else_body: list[Stmt]

    @property
    def has_else(self) -> bool:
        return len(self.else_body) > 0

@dataclass(eq=False)
class While(Stmt):
    test: Expr
    body: list[Stmt]

@dataclass(eq=False)
class Raise(Stmt):
    exc: Expr


# ====== Doppler-specific nodes ======
#
# The following nodes are special: they are never generated by the parser, but
# only by the doppler during redshift. In other words, they are not part of
# the proper AST-which-represent-the-syntax-of-the-language, but they are part
# of the AST-which-we-use-as-IR

@dataclass(eq=False)
class FQNConst(Expr):
    precedence = 100 # the highest
    fqn: FQN
