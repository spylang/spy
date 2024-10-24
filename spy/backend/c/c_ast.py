"""
Mini AST for C expressions. The goal is to provide a way to create
"readable" C expressions, without going crazy.

The non-trivial part is to generate the lowest possible number of parenthesis,
to increase readability.  In order to do that, we create a small AST of nodes
who knows about the C rules for operator precedence.

Supporting all possible C operators is not a goal: we will limit to the most
commonly used, and fallback to temporary variables for the other cases.

For completeness, here is the full table of operator precedence.

PREC  CATEGORY         OPERATOR            ASSOCIATIVITY
14    Postfix          () [] -> . ++ --    Left to right
13    Unary            + - ! ~ ++ --       Right to left
                       (type)* & sizeof
12    Multiplicative   * / %               Left to right
11    Additive         + -                 Left to right
10    Shift            << >>               Left to right
 9    Relational       < <= > >=           Left to right
 8    Equality         == !=               Left to right
 7    Bitwise AND      &                   Left to right
 6    Bitwise XOR      ^                   Left to right
 5    Bitwise OR       |                   Left to right
 4    Logical AND      &&                  Left to right
 3    Logical OR       ||                  Left to right
 2    Conditional      ?:                  Right to left
 1    Assignment       = += -= *=          Right to left
                       /= %=>>= <<=
                       &= ^= |=
 0    Comma            ,                   Left to right
"""

import re
from dataclasses import dataclass
from typing import ClassVar

def make_table(src: str) -> dict[str, int]:
    """
    Helper function to create a dict of operator precedence
    """
    table = {}
    src = src.strip()
    for line in src.splitlines():
        m = re.match(r' *(\d+): (.*)', line)
        if not m:
            raise ValueError('Syntax Error in the opeator table')
        prec = int(m.group(1))
        ops = m.group(2).split()
        for op in ops:
            table[op] = prec
    return table


@dataclass
class Expr:

    def precedence(self) -> int:
        raise NotImplementedError

    def __str__(self) -> str:
        """
        Convert the AST into C code
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        return f'<{cls}(...)>'

@dataclass
class Literal(Expr):
    """
    A constant or an identifier
    """
    value: str

    def precedence(self) -> int:
        return 100 # supposedly the highest

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_bytes(cls, b: bytes) -> 'Literal':
        """
        Transform the given bytearray into a C literal surrounded by double
        quotes, taking care of escaping.
        """
        def char_repr(val: int) -> str:
            ch = chr(val)
            if val in (ord('\\'), ord('"')):
                return rf'\{ch}'
            elif 32 <= val < 127:
                return ch
            return rf'\x{val:02x}' # :x is "hex format"

        lit = ''.join([char_repr(val) for val in b])
        return Literal(f'"{lit}"')


@dataclass
class Void(Expr):
    """
    This is a special case. It is used to represent a 'void' expression in the
    virtual stack (e.g. for the pattern 'load_const None; return'), but it's
    not a valid C expression, because C doesn't allow void values to be passed
    around.

    As such, we need to special-case it in all the places where it could be
    used.
    """

    _singleton: ClassVar['Void']

    def __new__(cls) -> 'Void':
        return cls._singleton

    def precedence(self) -> int:
        return 100

    def __str__(self) -> str:
        raise ValueError('You should never call Void.str(). '
                         'You should special-case your code to '
                         'handle this case specifically')

Void._singleton = object.__new__(Void)

@dataclass
class BinOp(Expr):
    op: str
    left: Expr
    right: Expr

    _table = make_table("""
        12: * / %
        11: + -
        10: << >>
         9: < <= > >=
         8: == !=
         7: &
         6: ^
         5: |
         4: &&
         3: ||
         1: =
    """)

    def precedence(self) -> int:
        assert self.op in self._table, f'Unknown operator {self.op}'
        return self._table[self.op]

    def __str__(self) -> str:
        l = str(self.left)
        r = str(self.right)
        if self.left.precedence() < self.precedence():
            l = f'({l})'
        if self.right.precedence() < self.precedence():
            r = f'({r})'
        return f'{l} {self.op} {r}'


@dataclass
class UnaryOp(Expr):
    op: str
    value: Expr

    _table = make_table("""
        13: + - ! ~ &
    """)

    def precedence(self) -> int:
        assert self.op in self._table, f'Unknown operator {self.op}'
        return self._table[self.op]

    def __str__(self) -> str:
        v = str(self.value)
        if self.value.precedence() < self.precedence():
            v = f'({v})'
        return f'{self.op}{v}'

@dataclass
class Call(Expr):
    func: str
    args: list[Expr]

    def precedence(self) -> int:
        return 14

    def __str__(self) -> str:
        args = [str(arg) for arg in self.args if not isinstance(arg, Void)]
        arglist = ', '.join(args)
        return f'{self.func}({arglist})'

@dataclass
class Arrow(Expr):
    ptr: Expr
    field: str

    def precedence(self) -> int:
        return 14

    def __str__(self) -> str:
        return f'{self.ptr}->{self.field}'

@dataclass
class SPyField(Expr):
    """
    Special case of Arrow.

    Here it assumes that `ptr` is a SPy ptr, i.e. a struct with a `.p` field,
    and dereferences that.
    """
    ptr: Expr
    field: str

    def precedence(self) -> int:
        return 14

    def __str__(self) -> str:
        return f'{self.ptr}.p->{self.field}'
