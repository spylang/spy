from spy.parser import Parser
from spy import ast

class AnyLocClass:

    def __repr__(self):
        return '<ANYLOC>'

    def __eq__(self, other):
        return True

ANYLOC = AnyLocClass()

class TestParser:

    def parse(self, src):
        p = Parser.from_string(src, dedent=True)
        return p.parse()

    def test_Module(self):
        mod = self.parse("""
        def foo() -> void:
            pass
        """)
        expected = ast.Module(
            loc = ANYLOC,
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
