from typing import Optional, NoReturn
import textwrap
import ast as py_ast
import astpretty
import spy.ast
from spy.location import Loc
from spy.errors import SPyCompileError, SPyParseError

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
        py_mod.compute_all_locs(self.filename)
        return self.to_Module(py_mod)

    def error(self, loc: Loc, message: str) -> NoReturn:
        raise SPyParseError(loc, message)

    def to_Module(self, py_mod: py_ast.Module) -> spy.ast.Module:
        mod = spy.ast.Module(filename=self.filename, decls=[])
        for py_stmt in py_mod.body:
            if isinstance(py_stmt, py_ast.FunctionDef):
                funcdef = self.to_FuncDef(py_stmt)
                mod.decls.append(funcdef)
            else:
                assert False, 'XXX'
        #
        return mod

    def to_FuncDef(self, py_funcdef: py_ast.FunctionDef) -> spy.ast.FuncDef:
        if py_funcdef.decorator_list:
            loc = py_funcdef.decorator_list[0].loc
            self.error(loc, 'decorators are not supported yet')
        #
        loc = py_funcdef.loc
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
            self.error(func_loc, 'missing return type')
        #
        return spy.ast.FuncDef(
            loc = py_funcdef.loc,
            name = py_funcdef.name,
            args = args,
            return_type = py_returns,
            body = py_funcdef.body,
        )

    def to_FuncArgs(self, py_args: py_ast.arguments) -> list[spy.ast.FuncArg]:
        if py_args.vararg:
            self.error(py_args.vararg.loc, '*args is not supported yet')
        if py_args.kwarg:
            self.error(py_args.kwarg.loc, '**kwargs is not supported yet')
        if py_args.defaults:
            self.error(py_args.defaults[0].loc,
                       'default arguments are not supported yet')
        if py_args.posonlyargs:
            self.error(py_args.posonlyargs[0].loc,
                       'positional-only arguments are not supported yet')
        if py_args.kwonlyargs:
            self.error(py_args.kwonlyargs[0].loc,
                       'keyword-only arguments are not supported yet')
        assert not py_args.kw_defaults
        #
        return [self.to_FuncArg(py_arg) for py_arg in py_args.args]

    def to_FuncArg(self, py_arg: py_ast.arg) -> spy.ast.FuncArg:
        loc = py_arg.loc
        if py_arg.annotation is None:
            self.error(loc, f"missing type for argument '{py_arg.arg}'")
        #
        return spy.ast.FuncArg(
            loc = loc,
            name = py_arg.arg,
            type = py_arg.annotation,
        )



def main() -> None:
    import sys
    p = Parser.from_filename(sys.argv[1])
    try:
        mod = p.parse()
    except SPyCompileError as e:
        print(e)
    else:
        mod.pp()

if __name__ == '__main__':
    main()
