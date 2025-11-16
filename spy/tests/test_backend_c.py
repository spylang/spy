"""
Unit tests for the C backend.

This is just a small part of the tests: the majority of the functionality is
tested by tests/compiler/*.py.
"""

from spy.backend.c.c_ast import BinOp, Literal, UnaryOp, make_table
from spy.backend.c.context import C_Ident


class TestExpr:
    def test_make_table(self):
        table = make_table("""
        12: * /
        11: + -
         8: ==
        """)
        assert table == {
            "*": 12,
            "/": 12,
            "+": 11,
            "-": 11,
            "==": 8,
        }

    def test_BinOp1(self):
        # fmt: off
        expr = BinOp("*",
            left = BinOp("+",
                left = Literal("1"),
                right = Literal("2")
            ),
            right = Literal("3")
        )
        # fmt: on
        assert str(expr) == "(1 + 2) * 3"

    def test_BinOp2(self):
        # fmt: off
        expr = BinOp("*",
            left = Literal("1"),
            right = BinOp("+",
                left = Literal("2"),
                right = BinOp("*",
                    left = Literal("3"),
                    right = Literal("4")
                )
            )
        )
        # fmt: on
        assert str(expr) == "1 * (2 + 3 * 4)"

    def test_UnaryOp(self):
        # fmt: off
        expr = UnaryOp("-",
            value=BinOp("*",
                left=Literal("1"),
                right=Literal("2"),
            ),
        )
        # fmt: on
        assert str(expr) == "-(1 * 2)"

    def test_Literal_from_bytes(self):
        def cstr(b: bytes) -> str:
            return str(Literal.from_bytes(b))

        #
        assert cstr(b"--hello--") == '"--hello--"'
        assert cstr(b'--"hello"--') == r'"--\"hello\"--"'
        assert cstr(rb"--aa\bb--") == r'"--aa\\bb--"'
        assert cstr(b"--\x00--\n--\xff--") == r'"--\x00--\x0a--\xff--"'
        assert cstr(b"\nball") == r'"\x0a""ball"'
        assert cstr(b"ball\n") == r'"ball\x0a"'
        assert cstr(b"ball\n\nball") == r'"ball\x0a\x0a""ball"'
        assert cstr(b"\x00\x01\x02") == r'"\x00\x01\x02"'


def test_check_c_preserve():
    for naming in C_Ident.C_KEYWORDS:
        c_naming = C_Ident(naming)
        assert f"{c_naming}" == f"{naming}$"


def test_check_non_c_preserve():
    namings = (
        "dEfault",  # C is case-sensitive, so only `default` is reserved
        "myName",
        "__name_s",
    )
    for naming in namings:
        c_naming = C_Ident(naming)
        assert f"{c_naming}" == f"{naming}"
