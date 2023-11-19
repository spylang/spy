from typing import Optional, NoReturn, Any
import textwrap
import ast as py_ast
import spy.ast
from spy.fqn import FQN
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
        return self.from_py_Module(py_mod)

    def error(self, primary: str, secondary: str, loc: Loc) -> NoReturn:
        raise SPyParseError.simple(primary, secondary, loc)

    def unsupported(self, node: py_ast.AST,
                    reason: Optional[str] = None) -> NoReturn:
        """
        Emit a nice error in case we encounter an unsupported AST node.
        """
        if reason is None:
            reason = node.__class__.__name__
        self.error(f'not implemented yet: {reason}',
                   'this is not yet supported by SPy', node.loc)

    def from_py_Module(self, py_mod: py_ast.Module) -> spy.ast.Module:
        mod = spy.ast.Module(filename=self.filename, decls=[])
        for py_stmt in py_mod.body:
            if isinstance(py_stmt, py_ast.FunctionDef):
                funcdef = self.from_py_FuncionDef(py_stmt)
                mod.decls.append(funcdef)
            elif isinstance(py_stmt, py_ast.AnnAssign):
                vardef = self.from_py_stmt_AnnAssign(py_stmt)
                globvar = spy.ast.GlobalVarDef(vardef)
                mod.decls.append(globvar)
            elif isinstance(py_stmt, py_ast.ImportFrom):
                importdecls = self.from_py_ImportFrom(py_stmt)
                mod.decls += importdecls
            else:
                msg = 'only function and variable definitions are allowed at global scope'
                self.error(msg, 'this is not allowed here', py_stmt.loc)
        #
        return mod

    def from_py_FuncionDef(self,
                           py_funcdef: py_ast.FunctionDef
                           ) -> spy.ast.FuncDef:
        color: spy.ast.Color = 'red'
        for deco in py_funcdef.decorator_list:
            if (isinstance(deco, py_ast.Name) and deco.id == 'blue'):
                # @blue is special-cased
                color = 'blue'
            else:
                # other decorators are not supported:
                self.error('decorators are not supported yet',
                           'this is not supported', deco.loc)
        #
        loc = py_funcdef.loc
        name = py_funcdef.name
        args = self.from_py_arguments(color, py_funcdef.args)
        #
        py_returns = py_funcdef.returns
        if py_returns:
            return_type = self.from_py_expr(py_returns)
        elif color == 'blue':
            return_type = spy.ast.Name(py_funcdef.loc, 'object')
        else:
            # create a loc which points to the 'def foo' part. This is a bit
            # wrong, ideally we would like it to point to the END of the
            # argument list, but it's not a very high priority by now
            func_loc = loc.replace(
                line_end = loc.line_start,
                col_end = len('def ') + len(name)
            )
            self.error('missing return type', '', func_loc)
        #
        body = self.from_py_body(py_funcdef.body)
        return spy.ast.FuncDef(
            loc = py_funcdef.loc,
            color = color,
            name = py_funcdef.name,
            args = args,
            return_type = return_type,
            body = body,
        )

    def from_py_arguments(self,
                          color: spy.ast.Color,
                          py_args: py_ast.arguments
                          ) -> list[spy.ast.FuncArg]:
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
        return [self.from_py_arg(color, py_arg) for py_arg in py_args.args]

    def from_py_arg(self,
                    color: spy.ast.Color,
                    py_arg: py_ast.arg
                    ) -> spy.ast.FuncArg:
        if py_arg.annotation:
            spy_type = self.from_py_expr(py_arg.annotation)
        elif color == 'blue':
            spy_type = spy.ast.Name(py_arg.loc, 'object')
        else:
            self.error(f"missing type for argument '{py_arg.arg}'",
                       'type is missing here', py_arg.loc)
        #
        return spy.ast.FuncArg(
            loc = py_arg.loc,
            name = py_arg.arg,
            type = spy_type,
        )

    def from_py_ImportFrom(self,
                           py_imp: py_ast.ImportFrom) -> list[spy.ast.Import]:
        res = []
        for py_alias in py_imp.names:
            fqn = FQN(modname=py_imp.module, attr=py_alias.name)
            asname = py_alias.asname or py_alias.name
            res.append(spy.ast.Import(
                loc = py_imp.loc,
                loc_asname = py_alias.loc,
                fqn = fqn,
                asname = asname
            ))
        return res

    # ====== spy.ast.Stmt ======

    def from_py_body(self, py_body: list[py_ast.stmt]) -> list[spy.ast.Stmt]:
        return [self.from_py_stmt(py_stmt) for py_stmt in py_body]

    def from_py_stmt(self, py_node: py_ast.stmt) -> spy.ast.Stmt:
        return magic_dispatch(self, 'from_py_stmt', py_node)

    from_py_stmt_NotImplemented = unsupported

    def from_py_stmt_Pass(self, py_node: py_ast.Pass) -> spy.ast.Pass:
        return spy.ast.Pass(py_node.loc)

    def from_py_stmt_Expr(self, py_node: py_ast.Expr) -> spy.ast.StmtExpr:
        # note: this is NOT an expr in the proper sense: it's an expr used as
        # a statement (e.g., a function call). This is perfectly valid of
        # course.
        value = self.from_py_expr(py_node.value)
        return spy.ast.StmtExpr(py_node.loc, value)

    def from_py_stmt_Return(self, py_node: py_ast.Return) -> spy.ast.Return:
        # we make 'return' completely equivalent to 'return None' already
        # during parsing: this simplifies quite a bit the rest
        value: spy.ast.Expr
        if py_node.value is None:
            value = spy.ast.Constant(py_node.loc, None)
        else:
            value = self.from_py_expr(py_node.value)
        return spy.ast.Return(py_node.loc, value)

    def from_py_stmt_AnnAssign(self, py_node: py_ast.AnnAssign) -> spy.ast.VarDef:
        if not py_node.simple:
            self.error(f"not supported: assignments targets with parentheses",
                       "this is not supported", py_node.target.loc)
        # I don't think it's possible to generate an AnnAssign node with a
        # non-name target
        assert isinstance(py_node.target, py_ast.Name), 'WTF?'
        assert py_node.value is not None
        return spy.ast.VarDef(
            loc = py_node.loc,
            name = py_node.target.id,
            type = self.from_py_expr(py_node.annotation),
            value = self.from_py_expr(py_node.value)
        )

    def from_py_stmt_Assign(self, py_node: py_ast.Assign) -> spy.ast.Stmt:
        # Assign can be pretty complex: it can have multiple targets, and a
        # target can be a Tuple or List in case of unpacking. For now, we
        # support only the very simple case of single assign to a Name.
        if len(py_node.targets) != 1:
            self.unsupported(py_node, 'assign to multiple targets')
        py_target = py_node.targets[0]
        if not isinstance(py_target, py_ast.Name):
            self.unsupported(py_target, 'assign to complex expressions')
        return spy.ast.Assign(
            loc = py_node.loc,
            target_loc = py_target.loc,
            target = py_target.id,
            value = self.from_py_expr(py_node.value)
        )

    def from_py_stmt_If(self, py_node: py_ast.If) -> spy.ast.If:
        return spy.ast.If(
            loc = py_node.loc,
            test = self.from_py_expr(py_node.test),
            then_body = self.from_py_body(py_node.body),
            else_body = self.from_py_body(py_node.orelse),
        )

    def from_py_stmt_While(self, py_node: py_ast.While) -> spy.ast.While:
        if py_node.orelse:
            self.unsupported(py_node, '`else` clause in `while` loops')
        return spy.ast.While(
            loc = py_node.loc,
            test = self.from_py_expr(py_node.test),
            body = self.from_py_body(py_node.body)
        )

    # ====== spy.ast.Expr ======

    def from_py_expr(self, py_node: py_ast.expr) -> spy.ast.Expr:
        return magic_dispatch(self, 'from_py_expr', py_node)

    from_py_expr_NotImplemented = unsupported

    def from_py_expr_Name(self, py_node: py_ast.Name) -> spy.ast.Name:
        return spy.ast.Name(py_node.loc, py_node.id)

    def from_py_expr_Constant(self, py_node: py_ast.Constant) -> spy.ast.Constant:
        assert py_node.kind is None  # I don't know what is 'kind' here
        return spy.ast.Constant(py_node.loc, py_node.value)

    def from_py_expr_Subscript(self, py_node: py_ast.Subscript) -> spy.ast.GetItem:
        value = self.from_py_expr(py_node.value)
        index = self.from_py_expr(py_node.slice)
        return spy.ast.GetItem(py_node.loc, value, index)

    def from_py_expr_List(self, py_node: py_ast.List) -> spy.ast.List:
        items = [self.from_py_expr(py_item) for py_item in py_node.elts]
        return spy.ast.List(py_node.loc, items)

    def from_py_expr_BinOp(self, py_node: py_ast.BinOp) -> spy.ast.BinOp:
        left = self.from_py_expr(py_node.left)
        right = self.from_py_expr(py_node.right)
        #
        # some magic to automatically find the correct spy.ast.* class
        opname = type(py_node.op).__name__
        if opname == 'Mult':
            opname = 'Mul'
        elif opname == 'MatMult':
            opname = 'MatMul'
        spy_cls = getattr(spy.ast, opname, None)
        assert spy_cls is not None, f'Unkown operator: {opname}'
        return spy_cls(py_node.loc, left, right)

    def from_py_expr_UnaryOp(self, py_node: py_ast.UnaryOp) -> spy.ast.Expr:
        value = self.from_py_expr(py_node.operand)
        opname = type(py_node.op).__name__
        # special-case -NUM
        if (opname == 'USub' and
            isinstance(value, spy.ast.Constant) and
            isinstance(value.value, int)):
            return spy.ast.Constant(value.loc, -value.value)
        # standard case
        spy_cls: Any
        if opname == 'UAdd':
            spy_cls = spy.ast.UnaryPos
        elif opname == 'USub':
            spy_cls = spy.ast.UnaryNeg
        elif opname == 'Invert':
            spy_cls = spy.ast.Invert
        elif opname == 'Not':
            spy_cls = spy.ast.Not
        else:
            assert False, f'Unkown operator: {opname}'
        #
        return spy_cls(py_node.loc, value)

    def from_py_expr_Compare(self, py_node: py_ast.Compare) -> spy.ast.CompareOp:
        if len(py_node.comparators) > 1:
            self.unsupported(py_node.comparators[1], 'chained comparisons')
        left = self.from_py_expr(py_node.left)
        right = self.from_py_expr(py_node.comparators[0])
        # some magic to automatically find the correct spy.ast.* class
        opname = type(py_node.ops[0]).__name__
        spy_cls = getattr(spy.ast, opname, None)
        assert spy_cls is not None, f'Unkown operator: {opname}'
        return spy_cls(py_node.loc, left, right)

    def from_py_expr_Call(self, py_node: py_ast.Call) -> spy.ast.Call:
        if py_node.keywords:
            self.unsupported(py_node.keywords[0], 'keyword arguments')
        return spy.ast.Call(
            loc = py_node.loc,
            func = self.from_py_expr(py_node.func),
            args = [self.from_py_expr(py_arg) for py_arg in py_node.args]
        )
