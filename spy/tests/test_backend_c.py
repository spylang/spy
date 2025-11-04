"""
Unit tests for the C backend.

This is just a small part of the tests: the majority of the functionality is
tested by tests/compiler/*.py.
"""

from typing import cast

import pytest

from spy import ast
from spy.backend.c.c_ast import BinOp, Literal, UnaryOp, make_table
from spy.backend.c.cmodwriter import CModuleWriter
from spy.backend.c.context import Context
from spy.backend.c.cwriter import CFuncWriter
from spy.fqn import FQN
from spy.location import Loc
from spy.tests.support import CompilerTest, only_interp
from spy.textbuilder import TextBuilder
from spy.vm.b import B
from spy.vm.function import W_ASTFunc
from spy.vm.modules.types import TYPES


class _StubCModuleWriter:
    """Minimal stub to satisfy CFuncWriter during unit tests."""

    def __init__(self) -> None:
        self.tbc: TextBuilder = TextBuilder(use_colors=False)
        self.tbc_globals: TextBuilder = TextBuilder(use_colors=False)
        self._counter: int = 0

    def new_global_var(self, prefix: str) -> str:
        name = f"SPY_g_{prefix}{self._counter}"
        self._counter += 1
        return name


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


@only_interp
class TestExprWType(CompilerTest):
    def redshift_module(self, src: str, *, modname: str = "test") -> str:
        self.write_file(f"{modname}.spy", src)
        self.vm.import_(modname)
        self.vm.redshift(error_mode="eager")
        return modname

    def make_writer(self, fullname: str) -> tuple[CFuncWriter, ast.FuncDef]:
        fqn = FQN(fullname)
        w_func = self.vm.lookup_global(fqn)
        assert isinstance(w_func, W_ASTFunc)
        ctx = Context(self.vm)
        stub = _StubCModuleWriter()
        writer = CFuncWriter(ctx, cast(CModuleWriter, stub), fqn, w_func)
        return writer, w_func.funcdef

    @staticmethod
    def return_expr(funcdef: ast.FuncDef) -> ast.Expr:
        for stmt in funcdef.body:
            if isinstance(stmt, ast.Return):
                return stmt.value
        raise AssertionError("return statement not found")

    def test_constants(self):
        modname = self.redshift_module(
            """
            def const_bool() -> bool:
                return True

            def const_int() -> i32:
                return 7

            def const_float() -> f64:
                return 1.5

            def const_none() -> None:
                return None

            def const_str() -> str:
                return "hi"
            """
        )

        expectations = {
            "const_bool": B.w_bool,
            "const_int": B.w_i32,
            "const_float": B.w_f64,
            "const_none": TYPES.w_NoneType,
            "const_str": B.w_str,
        }

        for name, expected in expectations.items():
            writer, funcdef = self.make_writer(f"{modname}::{name}")
            expr = self.return_expr(funcdef)
            assert writer.expr_w_type(expr) is expected

    def test_name_local_and_call(self):
        modname = self.redshift_module(
            """
            def identity(x: i32) -> i32:
                return x

            def call_identity(x: i32) -> i32:
                return identity(x)
            """
        )

        writer_id, funcdef_id = self.make_writer(f"{modname}::identity")
        expr_id = self.return_expr(funcdef_id)
        assert writer_id.expr_w_type(expr_id) is B.w_i32

        writer_call, funcdef_call = self.make_writer(f"{modname}::call_identity")
        expr_call = self.return_expr(funcdef_call)
        assert writer_call.expr_w_type(expr_call) is B.w_i32

    def test_name_outer_cell_and_fqn_const(self):
        modname = self.redshift_module(
            """
            var G: i32 = 5

            def return_global() -> i32:
                return G

            def inc(x: i32) -> i32:
                return x + 1

            def return_inc() -> object:
                return inc
            """
        )

        writer_global, funcdef_global = self.make_writer(f"{modname}::return_global")
        expr_global = self.return_expr(funcdef_global)
        assert writer_global.expr_w_type(expr_global) is B.w_i32

        writer_inc, funcdef_inc = self.make_writer(f"{modname}::return_inc")
        expr_inc = self.return_expr(funcdef_inc)
        inc_fqn = FQN(f"{modname}::inc")
        w_inc = self.vm.lookup_global(inc_fqn)
        assert isinstance(w_inc, W_ASTFunc)
        expected_type = w_inc.w_functype
        assert writer_inc.expr_w_type(expr_inc) is expected_type

    def test_cmp_chain(self):
        modname = self.redshift_module(
            """
            def cmp_chain(a: i32, b: i32, c: i32) -> bool:
                return a < b < c
            """
        )

        writer, funcdef = self.make_writer(f"{modname}::cmp_chain")
        expr = self.return_expr(funcdef)
        assert writer.expr_w_type(expr) is B.w_bool

        writer.local_decls = writer.tbc.make_nested_builder()
        try:
            formatted = writer.fmt_expr(expr)
        finally:
            writer.local_decls = None

        expected = (
            "(SPY_t_cmp0 = a , SPY_t_cmp1 = b , SPY_t_cmp0 < SPY_t_cmp1)"
            " && (SPY_t_cmp0 = SPY_t_cmp1 , SPY_t_cmp1 = c , SPY_t_cmp0 < SPY_t_cmp1)"
        )
        assert str(formatted) == expected

    def test_cmp_op_direct(self):
        modname = self.redshift_module(
            """
            def placeholder() -> bool:
                return True
            """
        )

        writer, _ = self.make_writer(f"{modname}::placeholder")
        left = ast.Constant(Loc.fake(), 1)
        right = ast.Constant(Loc.fake(), 2)
        cmp_op = ast.CmpOp(Loc.fake(), "<", left, right)
        assert writer.expr_w_type(cmp_op) is B.w_bool

    def test_cmp_chain_mismatched_types(self):
        modname = self.redshift_module(
            """
            def placeholder() -> bool:
                return True
            """
        )

        writer, _ = self.make_writer(f"{modname}::placeholder")
        cmp0 = ast.CmpOp(
            Loc.fake(), "<", ast.Constant(Loc.fake(), 1), ast.Constant(Loc.fake(), 2)
        )
        cmp1 = ast.CmpOp(
            Loc.fake(), "<", ast.Constant(Loc.fake(), 2), ast.Constant(Loc.fake(), 3.5)
        )
        chain = ast.CmpChain(Loc.fake(), [cmp0, cmp1])

        writer.local_decls = writer.tbc.make_nested_builder()
        try:
            with pytest.raises(NotImplementedError, match="mismatched operand types"):
                writer.fmt_expr(chain)
        finally:
            writer.local_decls = None

    def test_cmp_chain_first_mismatch(self):
        modname = self.redshift_module(
            """
            def placeholder() -> bool:
                return True
            """
        )

        writer, _ = self.make_writer(f"{modname}::placeholder")
        cmp0 = ast.CmpOp(
            Loc.fake(), "<", ast.Constant(Loc.fake(), 1), ast.Constant(Loc.fake(), 2.5)
        )
        cmp1 = ast.CmpOp(
            Loc.fake(), "<", ast.Constant(Loc.fake(), 2.5), ast.Constant(Loc.fake(), 3)
        )
        chain = ast.CmpChain(Loc.fake(), [cmp0, cmp1])

        with pytest.raises(NotImplementedError, match="mismatched operand types"):
            writer.fmt_expr(chain)
