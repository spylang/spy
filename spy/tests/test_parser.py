import pytest
from spy.parser import Parser
from spy.errors import SPyParseError
from spy import ast

class AnyLocClass:

    def __repr__(self):
        return '<ANYLOC>'

    def __eq__(self, other):
        return True

ANYLOC: ast.Location = AnyLocClass()  # type:ignore

class TestParser:

    def parse(self, src) -> ast.Module:
        p = Parser.from_string(src, dedent=True)
        return p.parse()

    def test_Module(self):
        mod = self.parse("""
        def foo() -> void:
            pass
        """)
        expected = ast.Module(
            decls = [
                ast.FuncDef(
                    loc = ANYLOC,
                    name = 'foo',
                    args = ast.FuncArgs(),
                    return_type = ast.Name(loc=ANYLOC, id='void'),
                )
            ]
        )
        assert mod == expected

    def test_missing_return_type(self):
        with pytest.raises(SPyParseError, match="Missing return type"):
            mod = self.parse("""
            def foo():
                pass
            """)
