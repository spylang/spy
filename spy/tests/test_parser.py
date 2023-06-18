import ast as py_ast
from typing import Any
import textwrap
import pytest
import spy.ast
from spy.ast_dump import dump
from spy.parser import Parser
from spy.errors import SPyParseError


class TestParser:

    def parse(self, src) -> spy.ast.Module:
        p = Parser.from_string(src, dedent=True)
        return p.parse()

    def assert_dump(self, node: spy.ast.Node, expected: str):
        dumped = dump(node, use_colors=False)
        expected = textwrap.dedent(expected)
        assert dumped.strip() == expected.strip()

    def test_Module(self):
        mod = self.parse("""
        def foo() -> void:
            pass
        """)
        expected = """
        Module(
            decls=[
                FuncDef(
                    name='foo',
                    args=[],
                    return_type=py:Name(id='void', ctx=py:Load()),
                    body=[
                        py:Pass(),
                    ],
                ),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_FuncDef_arguments(self):
        mod = self.parse("""
        def foo(a: i32, b: float) -> void:
            pass
        """)
        expected = """
        Module(
            decls=[
                FuncDef(
                    name='foo',
                    args=[
                        FuncArg(
                            name='a',
                            type=py:Name(id='i32', ctx=py:Load()),
                        ),
                        FuncArg(
                            name='b',
                            type=py:Name(id='float', ctx=py:Load()),
                        ),
                    ],
                    return_type=py:Name(id='void', ctx=py:Load()),
                    body=[
                        py:Pass(),
                    ],
                ),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_FuncDef_errors(self):
        with pytest.raises(SPyParseError, match="missing return type"):
            mod = self.parse("""
            def foo():
                pass
            """)
        #
        with pytest.raises(SPyParseError, match=r"\*args is not supported yet"):
            mod = self.parse("""
            def foo(*args) -> void:
                pass
            """)
        #
        with pytest.raises(SPyParseError, match=r"\*\*kwargs is not supported yet"):
            mod = self.parse("""
            def foo(**kwargs) -> void:
                pass
            """)
        #
        with pytest.raises(SPyParseError,
                           match="default arguments are not supported yet"):
            mod = self.parse("""
            def foo(a: i32 = 42) -> void:
                pass
            """)
        #
        with pytest.raises(SPyParseError,
                           match="positional-only arguments are not supported yet"):
            mod = self.parse("""
            def foo(a: i32, /, b: i32) -> void:
                pass
            """)
        #
        with pytest.raises(SPyParseError,
                           match="keyword-only arguments are not supported yet"):
            mod = self.parse("""
            def foo(a: i32, *, b: i32) -> void:
                pass
            """)
        #
        with pytest.raises(SPyParseError, match="missing type for argument 'a'"):
            mod = self.parse("""
            def foo(a, b) -> void:
                pass
            """)
        #
        with pytest.raises(SPyParseError, match="decorators are not supported yet"):
            mod = self.parse("""
            @mydecorator
            def foo() -> void:
                pass
            """)


    def test_FuncDef_body(self):
        mod = self.parse("""
        def foo() -> i32:
            return 42
        """)
        funcdef = mod.decls[0]
        assert isinstance(funcdef, spy.ast.FuncDef)
        assert len(funcdef.body) == 1
        stmt = funcdef.body[0]
        assert isinstance(stmt, py_ast.Return)
