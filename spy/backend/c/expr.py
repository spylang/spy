"""
The goal of this module is to provide a way to create "readable" C
expressions, without going crazy.

This is used by CFuncWriter to translated IR stack operations into C
code. Imagine to have the following:
    load_const 1
    load_const 2
    i32_add
    load_const 3
    i32_mul

A trivial way to implement is to use a lot of temporary variables:
    int32_t tmp1 = 1;
    int32_t tmp2 = 2;
    int32_t tmp3 = tmp1 + tmp2;
    int32_t tmp4 = 3;
    int32_t tmp5 = tmp3 * tmp4;

The goal is to generate more readable code, such as:
    (1 + 2) * 3

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

def make_table(src):
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

    def str(self) -> str:
        """
        Convert the AST into C code
        """
        raise NotImplementedError


@dataclass
class Literal(Expr):
    """
    A constant or an identifier
    """
    value: str

    def precedence(self) -> int:
        return 100 # supposedly the highest

    def str(self) -> str:
        return self.value

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
    """)

    def precedence(self) -> int:
        assert self.op in self._table, f'Unknown operator {self.op}'
        return self._table[self.op]

    def str(self):
        l = self.left.str()
        r = self.right.str()
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
        13: + - ! ~
    """)

    def precedence(self) -> int:
        assert self.op in self._table, f'Unknown operator {self.op}'
        return self._table[self.op]

    def str(self):
        v = self.value.str()
        if self.value.precedence() < self.precedence():
            v = f'({v})'
        return f'{self.op}{v}'
