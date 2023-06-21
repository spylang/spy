from typing import Optional, NoReturn
import textwrap
import ast as py_ast
import spy.ast
from spy.location import Loc
from spy.errors import SPyCompileError, SPyParseError
from spy.util import magic_dispatch

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
    def from_filename(cls, filename: str) -> 'Parser':
        with open(filename) as f:
            src = f.read()
        return Parser(src, filename)

    def parse(self) -> spy.ast.Module:
        py_mod = py_ast.parse(self.src)
        assert isinstance(py_mod, py_ast.Module)
        py_mod.compute_all_locs(self.filename)
        return self.to_Module(py_mod)

    def error(self, primary: str, secondary: str, loc: Loc) -> NoReturn:
        raise SPyParseError.simple(primary, secondary, loc)

    def to_Node_NotImplemented(self, node: py_ast.AST) -> NoReturn:
        """
        Emit a nice error in case we encounter an unsupported AST node.
        """
        thing = node.__class__.__name__
        self.error(f'not implemented yet: {thing}',
                   'this is not yet supported by SPy', node.loc)

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
            self.error('decorators are not supported yet',
                       'this is not supported', loc)
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
            self.error('missing return type', '', func_loc)
        #
        return_type = self.to_Expr(py_returns)
        body = [self.to_Stmt(py_stmt) for py_stmt in py_funcdef.body]
        return spy.ast.FuncDef(
            loc = py_funcdef.loc,
            name = py_funcdef.name,
            args = args,
            return_type = return_type,
            body = body,
        )

    def to_FuncArgs(self, py_args: py_ast.arguments) -> list[spy.ast.FuncArg]:
        if py_args.vararg:
            self.error('*args is not supported yet',
                       'this is not supported', py_args.vararg.loc)
        if py_args.kwarg:
            self.error('**kwargs is not supported yet',
                       'this is not supported', py_args.kwarg.loc)
        if py_args.defaults:
            self.error('default arguments are not supported yet',
                       'this is not supported', py_args.defaults[0].loc)
        if py_args.posonlyargs:
            self.error('positional-only arguments are not supported yet',
                       'this is not supported', py_args.posonlyargs[0].loc)
        if py_args.kwonlyargs:
            self.error('keyword-only arguments are not supported yet',
                       'this is not supported', py_args.kwonlyargs[0].loc)
        assert not py_args.kw_defaults
        #
        return [self.to_FuncArg(py_arg) for py_arg in py_args.args]

    def to_FuncArg(self, py_arg: py_ast.arg) -> spy.ast.FuncArg:
        if py_arg.annotation is None:
            self.error(f"missing type for argument '{py_arg.arg}'",
                       'type is missing here', py_arg.loc)
        #
        return spy.ast.FuncArg(
            loc = py_arg.loc,
            name = py_arg.arg,
            type = self.to_Expr(py_arg.annotation),
        )

    # ====== spy.ast.Stmt ======

    def to_Stmt(self, py_node: py_ast.stmt) -> spy.ast.Stmt:
        return magic_dispatch(self, 'to_Stmt', py_node)

    to_Stmt_NotImplemented = to_Node_NotImplemented

    def to_Stmt_Pass(self, py_node: py_ast.Pass) -> spy.ast.Pass:
        return spy.ast.Pass(py_node.loc)

    def to_Stmt_Return(self, py_node: py_ast.Return) -> spy.ast.Return:
        # we make 'return' completely equivalent to 'return None' already
        # during parsing: this simplifies quite a bit the rest
        value: spy.ast.Expr
        if py_node.value is None:
            value = spy.ast.Name(py_node.loc, 'None')
        else:
            value = self.to_Expr(py_node.value)
        return spy.ast.Return(py_node.loc, value)

    # ====== spy.ast.Expr ======

    def to_Expr(self, py_node: py_ast.expr) -> spy.ast.Expr:
        return magic_dispatch(self, 'to_Expr', py_node)

    to_Expr_NotImplemented = to_Node_NotImplemented

    def to_Expr_Name(self, py_node: py_ast.Name) -> spy.ast.Name:
        return spy.ast.Name(py_node.loc, py_node.id)

    def to_Expr_Constant(self, py_node: py_ast.Constant) -> spy.ast.Constant:
        assert py_node.kind is None  # I don't know what is 'kind' here
        return spy.ast.Constant(py_node.loc, py_node.value)

    def to_Expr_Subscript(self, py_node: py_ast.Subscript) -> spy.ast.GetItem:
        value = self.to_Expr(py_node.value)
        index = self.to_Expr(py_node.slice)
        return spy.ast.GetItem(py_node.loc, value, index)
