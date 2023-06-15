import textwrap
import ast as py_ast
import astpretty
import spy.ast

# monkey-patch python's AST to add a pp() method
py_ast.AST.pp = astpretty.pprint

def get_loc(node: py_ast.AST) -> spy.ast.Location:
    if hasattr(node, 'lineno'):
        return spy.ast.Location(
            line_start=node.lineno,
            line_end=node.end_lineno,
            col_start=node.col_offset,
            col_end=node.end_col_offset
        )
    else:
        return None

class Parser:
    """
    SPy parser: take source code as input, produce a SPy AST as output.

    This is a bit different than a "proper" parser because for now it relies
    on the Python's own parser: so the final result is produced by converting
    Python's AST into SPy's AST.

    The naming convention is the following:

      - Python's own `ast` module is imported as `py_ast`
      - Variables holding `py_ast` nodes are named `py_*`
      - `spy.ast` is the module which implements the SPy AST.
    """
    src: str
    filename: str

    def __init__(self, src: str, filename: str) -> None:
        self.src = src
        self.filename = filename

    @classmethod
    def from_string(cls, src: str, *, dedent: bool = False) -> 'Parser':
        if dedent:
            src = textwrap.dedent(src)
        return Parser(src, filename=None)

    @classmethod
    def from_filename(cls, filename: str) -> 'Parser':
        with open(filename) as f:
            src = f.read()
        return Parser(src, filename)

    def parse(self) -> spy.ast.Module:
        py_mod = py_ast.parse(self.src)
        assert isinstance(py_mod, py_ast.Module)
        return self.to_Module(py_mod)

    def to_Module(self, py_mod: py_ast.Module) -> spy.ast.Module:
        mod = spy.ast.Module(loc=get_loc(py_mod), decls=[])
        for py_stmt in py_mod.body:
            if isinstance(py_stmt, py_ast.FunctionDef):
                funcdef = self.to_FuncDef(py_stmt)
                mod.decls.append(funcdef)
            else:
                assert False, 'XXX'
        #
        return mod

    def to_FuncDef(self, py_funcdef: py_ast.FunctionDef) -> spy.ast.FuncDef:
        name = py_funcdef.name
        args = self.to_FuncArgs(py_funcdef.args)
        #
        py_returns = py_funcdef.returns
        if not isinstance(py_returns, py_ast.Name):
            assert False, 'XXX'
        return_type = spy.ast.Name(loc=get_loc(py_returns),
                                   id=py_returns.id)
        #
        return spy.ast.FuncDef(
            loc = get_loc(py_funcdef),
            name = py_funcdef.name,
            args = args,
            return_type = return_type
        )

    def to_FuncArgs(self, py_args: py_ast.arguments) -> spy.ast.FuncArgs:
        assert py_args.args == [], 'XXX'
        return spy.ast.FuncArgs()
