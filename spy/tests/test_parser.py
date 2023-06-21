import ast as py_ast
from typing import Any
import textwrap
import pytest
import spy.ast
from spy.ast_dump import dump
from spy.parser import Parser
from spy.errors import SPyParseError
from spy.tests.support import CompilerTest


class TestParser(CompilerTest):

    def parse(self, src) -> spy.ast.Module:
        srcfile = self.write_source('test.py', src)
        p = Parser.from_filename(str(srcfile))
        return p.parse()

    def assert_dump(self, node: spy.ast.Node, expected: str):
        dumped = dump(node, use_colors=False)
        expected = textwrap.dedent(expected)
        if '{tmpdir}' in expected:
            expected = expected.format(tmpdir=self.tmpdir)
        assert dumped.strip() == expected.strip()

    def test_Module(self):
        mod = self.parse("""
        def foo() -> void:
            pass
        """)
        expected = """
        Module(
            filename='{tmpdir}/test.py',
            decls=[
                FuncDef(
                    name='foo',
                    args=[],
                    return_type=Name(id='void'),
                    body=[
                        Pass(),
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
            filename='{tmpdir}/test.py',
            decls=[
                FuncDef(
                    name='foo',
                    args=[
                        FuncArg(
                            name='a',
                            type=Name(id='i32'),
                        ),
                        FuncArg(
                            name='b',
                            type=Name(id='float'),
                        ),
                    ],
                    return_type=Name(id='void'),
                    body=[
                        Pass(),
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
        expected = """
        FuncDef(
            name='foo',
            args=[],
            return_type=Name(id='i32'),
            body=[
                Return(
                    value=Constant(value=42),
                ),
            ],
        )
        """
        self.assert_dump(funcdef, expected)

    def test_empty_return(self):
        mod = self.parse("""
        def foo() -> void:
            return
        """)
        funcdef = mod.decls[0]
        expected = """
        FuncDef(
            name='foo',
            args=[],
            return_type=Name(id='void'),
            body=[
                Return(
                    value=Name(id='None'),
                ),
            ],
        )
        """
        self.assert_dump(funcdef, expected)

    ## def test_getitem(self):
    ##     mod = self.parse("""
    ##     def foo() -> void:
    ##         mylist[0]
    ##     """)
    ##     funcdef = mod.decls[0]
    ##     expected = """
    ##     FuncDef(
    ##         name='foo',
    ##         args=[],
    ##         return_type=Name(id='void'),
    ##         body=[
    ##             Return(
    ##                 value=Name(id='None'),
    ##             ),
    ##         ],
    ##     )
    ##     """
    ##     self.assert_dump(funcdef, expected)
