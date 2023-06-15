from typing import Optional
import textwrap
import ast as py_ast
import astpretty
import spy.ast
from spy.errors import SPyCompileError, SPyParseError

# monkey-patch python's AST to add a pp() method
py_ast.AST.pp = astpretty.pprint  # type:ignore

def get_loc(py_node: py_ast.AST) -> spy.ast.Location:
    if isinstance(py_node, py_ast.Module):
        raise TypeError('py_ast.Module does not have a location')
    #
    # all the other nodes should have a location. If they don't, we should
    # investigate and decide what to do
    assert hasattr(py_node, 'lineno')
    return spy.ast.Location(
        line_start = py_node.lineno,
        line_end = py_node.end_lineno,
        col_start = py_node.col_offset,
        col_end = py_node.end_col_offset
    )



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
        return Parser(src, filename='<string>')

    @classmethod
    def from_filename(cls, filename: str) -> 'Parser':
        with open(filename) as f:
            src = f.read()
        return Parser(src, filename)

    def parse(self) -> spy.ast.Module:
        py_mod = py_ast.parse(self.src)
        assert isinstance(py_mod, py_ast.Module)
        return self.to_Module(py_mod)

    def error(self, loc: spy.ast.Location, message: str) -> None:
        raise SPyParseError(self.filename, loc, message)

    def to_Module(self, py_mod: py_ast.Module) -> spy.ast.Module:
        mod = spy.ast.Module(decls=[])
        for py_stmt in py_mod.body:
            if isinstance(py_stmt, py_ast.FunctionDef):
                funcdef = self.to_FuncDef(py_stmt)
                mod.decls.append(funcdef)
            else:
                assert False, 'XXX'
        #
        return mod

    def to_FuncDef(self, py_funcdef: py_ast.FunctionDef) -> spy.ast.FuncDef:
        loc = get_loc(py_funcdef)
        name = py_funcdef.name
        args = self.to_FuncArgs(py_funcdef.args)
        #
        py_returns = py_funcdef.returns
        if py_returns is None:
            # create a loc which points to the 'def foo' part. This is a bit
            # wrong, ideally we would like it to point to the END of the
            # argument list, but it's not a very high priority by now
            func_loc = loc.replace(
                line_end = loc.line_start,
                col_end = len('def ') + len(name)
            )
            self.error(func_loc, 'Missing return type')
        #
        if not isinstance(py_returns, py_ast.Name):
            # we want to handle more complex expressions
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

def main() -> None:
    import sys
    p = Parser.from_filename(sys.argv[1])
    try:
        mod = p.parse()
    except SPyCompileError as e:
        print(e)
    else:
        print('Parsing OK')

if __name__ == '__main__':
    main()
