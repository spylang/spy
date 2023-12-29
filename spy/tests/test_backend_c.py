"""
Unit tests for the C backend.

This is just a small part of the tests: the majority of the functionality is
tested by tests/compiler/*.py.
"""

from spy.backend.c.c_ast import make_table, Literal, BinOp, UnaryOp

class TestExpr:

    def test_make_table(self):
        table = make_table("""
        12: * /
        11: + -
         8: ==
        """)
        assert table == {
            '*': 12,
            '/': 12,
            '+': 11,
            '-': 11,
            '==': 8,
        }

    def test_BinOp1(self):
        expr = BinOp('*',
            left = BinOp('+',
                left = Literal('1'),
                right = Literal('2')
            ),
            right = Literal('3')
        )
        assert str(expr) == '(1 + 2) * 3'

    def test_BinOp2(self):
        expr = BinOp('*',
            left = Literal('1'),
            right = BinOp('+',
                left = Literal('2'),
                right = BinOp('*',
                    left = Literal('3'),
                    right = Literal('4')
                )
            )
        )
        assert str(expr) == '1 * (2 + 3 * 4)'

    def test_UnaryOp(self):
        expr = UnaryOp('-',
            value = BinOp('*',
                left = Literal('1'),
                right = Literal('2'),
            )
        )
        assert str(expr) == '-(1 * 2)'

    def test_Literal_from_bytes(self):
        def cstr(b: bytes) -> str:
            return str(Literal.from_bytes(b))
        #
        assert cstr(b'--hello--') == '"--hello--"'
        assert cstr(b'--"hello"--') == r'"--\"hello\"--"'
        assert cstr(rb'--aa\bb--') == r'"--aa\\bb--"'
        assert cstr(b'--\x00--\n--\xff--') == r'"--\x00--\x0a--\xff--"'
