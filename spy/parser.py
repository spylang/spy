import ast as py_ast
import typing
from types import NoneType
from typing import NoReturn, Optional

import spy.ast
from spy.analyze.symtable import ImportRef
from spy.errors import SPyError
from spy.fqn import FQN
from spy.location import Loc
from spy.magic_py_parse import magic_py_parse
from spy.util import magic_dispatch


def is_py_Name(py_expr: py_ast.expr, expected: str) -> bool:
    return isinstance(py_expr, py_ast.Name) and py_expr.id == expected


def parse_special_decorator(py_expr: py_ast.expr) -> Optional[str]:
    """
    If the decorator is a simple @name or @name.attr, return them as
    strings. Else, return None.
    """
    if isinstance(py_expr, py_ast.Name):
        return py_expr.id

    if isinstance(py_expr, py_ast.Attribute) and isinstance(py_expr.value, py_ast.Name):
        a = py_expr.value.id
        b = py_expr.attr
        return f"{a}.{b}"

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
    for_loop_seq: int  # counter for for loops within the current function

    def __init__(self, src: str, filename: str) -> None:
        self.src = src
        self.filename = filename
        self.for_loop_seq = 0

    @classmethod
    def from_filename(cls, filename: str) -> "Parser":
        with open(filename) as f:
            src = f.read()
        return Parser(src, filename)

    def parse(self) -> spy.ast.Module:
        py_mod = magic_py_parse(self.src, self.filename)
        assert isinstance(py_mod, py_ast.Module)
        py_mod.compute_all_locs(self.filename)
        return self.from_py_Module(py_mod)

    def error(self, primary: str, secondary: str, loc: Loc) -> NoReturn:
        raise SPyError.simple("W_ParseError", primary, secondary, loc)

    def unsupported(self, node: py_ast.AST, reason: Optional[str] = None) -> NoReturn:
        """
        Emit a nice error in case we encounter an unsupported AST node.
        """
        if reason is None:
            reason = node.__class__.__name__
        self.error(f"not implemented yet: {reason}", "this is not supported", node.loc)

    def get_docstring_maybe(
        self, body: list[py_ast.stmt]
    ) -> tuple[Optional[str], list[py_ast.stmt]]:
        """
        Extract the docstring from a list of statements.
        """
        if not body:
            return None, body

        # Check if the first statement is an expression with a string constant
        first_stmt = body[0]
        if (
            isinstance(first_stmt, py_ast.Expr)
            and isinstance(first_stmt.value, py_ast.Constant)
            and isinstance(first_stmt.value.value, str)
        ):
            return first_stmt.value.value, body[1:]

        return None, body

    def from_py_Module(self, py_mod: py_ast.Module) -> spy.ast.Module:
        loc = Loc(self.filename, 1, 1, 0, -1)

        # Extract module docstring
        docstring, py_body = self.get_docstring_maybe(py_mod.body)

        mod = spy.ast.Module(
            loc=loc, filename=self.filename, decls=[], docstring=docstring
        )

        for py_stmt in py_body:
            if isinstance(py_stmt, py_ast.FunctionDef):
                funcdef = self.from_py_stmt_FunctionDef(py_stmt)
                globfunc = spy.ast.GlobalFuncDef(funcdef.loc, funcdef)
                mod.decls.append(globfunc)
            elif isinstance(py_stmt, py_ast.ClassDef):
                classdef = self.from_py_stmt_ClassDef(py_stmt)
                globclass = spy.ast.GlobalClassDef(classdef.loc, classdef)
                mod.decls.append(globclass)
            elif isinstance(py_stmt, py_ast.AnnAssign):
                vardef, assign = self.from_py_AnnAssign(py_stmt, is_global=True)
                assert assign is not None
                globvar = spy.ast.GlobalVarDef(py_stmt.loc, vardef, assign)
                mod.decls.append(globvar)
            elif isinstance(py_stmt, py_ast.Assign):
                vardef, assign = self.from_py_global_Assign(py_stmt)
                globvar = spy.ast.GlobalVarDef(py_stmt.loc, vardef, assign)
                mod.decls.append(globvar)
            elif isinstance(py_stmt, py_ast.ImportFrom):
                importdecls = self.from_py_ImportFrom(py_stmt)
                mod.decls += importdecls
            elif isinstance(py_stmt, py_ast.Import):
                importdecls = self.from_py_Import(py_stmt)
                mod.decls += importdecls
            else:
                msg = (
                    "only function and variable definitions are allowed at global scope"
                )
                self.error(msg, "this is not allowed here", py_stmt.loc)
        return mod

    def from_py_stmt_FunctionDef(
        self, py_funcdef: py_ast.FunctionDef
    ) -> spy.ast.FuncDef:
        color: spy.ast.Color = "red"
        func_kind: spy.ast.FuncKind = "plain"
        decorators: list[spy.ast.Expr] = []

        for deco in py_funcdef.decorator_list:
            d = parse_special_decorator(deco)
            # @blue.* are special cased
            if d == "blue":
                color = "blue"
            elif d == "blue.generic":
                color = "blue"
                func_kind = "generic"
            elif d == "blue.metafunc":
                color = "blue"
                func_kind = "metafunc"
            else:
                # other decorators are stored as general decorators
                decorators.append(self.from_py_expr(deco))
        #
        loc = py_funcdef.loc
        name = py_funcdef.name
        args, vararg = self.from_py_arguments(color, py_funcdef.args)
        #
        py_returns = py_funcdef.returns
        if py_returns:
            return_type = self.from_py_expr(py_returns)
        elif color == "blue":
            # we need to synthesize a reasonable Loc for the return type. See
            # also test_FuncDef_prototype_loc.
            if len(args) == 0:
                # no arguments: this is though because the python parser
                # doesn't tell us e.g. where the '()' or ':' are. The only
                # reasonable thing we can do is to keep the whole line where
                # the function starts
                retloc = py_funcdef.loc.replace(
                    line_end=py_funcdef.loc.line_start, col_end=-1
                )
            else:
                # we declare the function prototype ends at the end of the
                # line where the last argument is
                l = args[-1].loc
                retloc = l.replace(col_end=-1)
            return_type = spy.ast.Name(retloc, "dynamic")
        else:
            # create a loc which points to the 'def foo' part. This is a bit
            # wrong, ideally we would like it to point to the END of the
            # argument list, but it's not a very high priority by now
            func_loc = loc.replace(
                line_end=loc.line_start, col_end=len("def ") + len(name)
            )
            self.error("missing return type", "", func_loc)

        docstring, py_body = self.get_docstring_maybe(py_funcdef.body)
        self.for_loop_seq = 0  # reset counter for this function
        body = self.from_py_body(py_body)

        return spy.ast.FuncDef(
            loc=py_funcdef.loc,
            color=color,
            kind=func_kind,
            name=py_funcdef.name,
            args=args,
            vararg=vararg,
            return_type=return_type,
            body=body,
            docstring=docstring,
            decorators=decorators,
        )

    def from_py_arguments(
        self, color: spy.ast.Color, py_args: py_ast.arguments
    ) -> tuple[list[spy.ast.FuncArg], Optional[spy.ast.FuncArg]]:
        vararg = None
        if py_args.vararg:
            vararg = self.from_py_arg(color, py_args.vararg)
        if py_args.kwarg:
            self.error(
                "**kwargs is not supported yet",
                "this is not supported",
                py_args.kwarg.loc,
            )
        if py_args.defaults:
            self.error(
                "default arguments are not supported yet",
                "this is not supported",
                py_args.defaults[0].loc,
            )
        if py_args.posonlyargs:
            self.error(
                "positional-only arguments are not supported yet",
                "this is not supported",
                py_args.posonlyargs[0].loc,
            )
        if py_args.kwonlyargs:
            self.error(
                "keyword-only arguments are not supported yet",
                "this is not supported",
                py_args.kwonlyargs[0].loc,
            )
        assert not py_args.kw_defaults
        #
        args = [self.from_py_arg(color, py_arg) for py_arg in py_args.args]
        return args, vararg

    def from_py_arg(self, color: spy.ast.Color, py_arg: py_ast.arg) -> spy.ast.FuncArg:
        if py_arg.annotation:
            spy_type = self.from_py_expr(py_arg.annotation)
        elif color == "blue":
            spy_type = spy.ast.Name(py_arg.loc, "dynamic")
        else:
            self.error(
                f"missing type for argument '{py_arg.arg}'",
                "type is missing here",
                py_arg.loc,
            )
        #
        return spy.ast.FuncArg(
            loc=py_arg.loc,
            name=py_arg.arg,
            type=spy_type,
        )

    def from_py_stmt_ClassDef(self, py_classdef: py_ast.ClassDef) -> spy.ast.ClassDef:
        if py_classdef.bases:
            self.error(
                "base classes not supported yet",
                "this is not supported",
                py_classdef.bases[0].loc,
            )

        if py_classdef.keywords:
            self.error(
                "keywords in classes not supported yet",
                "this is not supported",
                py_classdef.keywords[0].loc,
            )

        # decorators are not supported yet, but @struct and @typelif are
        # special-cased
        struct_loc: Optional[Loc] = None
        typelift_loc: Optional[Loc] = None
        for py_deco in py_classdef.decorator_list:
            if is_py_Name(py_deco, "struct"):
                struct_loc = py_deco.loc
            elif is_py_Name(py_deco, "typelift"):
                typelift_loc = py_deco.loc
            else:
                self.error(
                    "class decorators not supported yet",
                    "this is not supported",
                    py_deco.loc,
                )

        kind: spy.ast.ClassKind
        if struct_loc and typelift_loc:
            self.error(
                "cannot use both @struct and @typelift", "this is invalid", typelift_loc
            )
        elif struct_loc:
            kind = "struct"
        elif typelift_loc:
            kind = "typelift"
        else:
            kind = "class"

        docstring, py_class_body = self.get_docstring_maybe(py_classdef.body)

        # only few kind of declarations are supported inside a "class:" block
        fields: list[spy.ast.VarDef] = []
        body: list[spy.ast.Stmt] = []
        for py_stmt in py_class_body:
            if isinstance(py_stmt, py_ast.AnnAssign):
                vardef, assign = self.from_py_AnnAssign(py_stmt)
                if assign is not None:
                    self.error(
                        "default values in fields not supported yet",
                        "this is not supported",
                        assign.loc,
                    )
                fields.append(vardef)
            else:
                stmt = self.from_py_stmt(py_stmt)
                if isinstance(stmt, (spy.ast.FuncDef, spy.ast.If, spy.ast.Pass)):
                    body.append(stmt)
                else:
                    STMT = stmt.__class__.__name__
                    msg = f"`{STMT}` not supported inside a classdef"
                    self.error(msg, "this is not supported", stmt.loc)

        return spy.ast.ClassDef(
            loc=py_classdef.loc,
            name=py_classdef.name,
            kind=kind,
            fields=fields,
            body=body,
            docstring=docstring,
        )

    def from_py_ImportFrom(self, py_imp: py_ast.ImportFrom) -> list[spy.ast.Import]:
        res = []
        for py_alias in py_imp.names:
            assert py_imp.module is not None
            impref = ImportRef(py_imp.module, py_alias.name)
            asname = py_alias.asname or py_alias.name
            res.append(
                spy.ast.Import(
                    loc=py_imp.loc, loc_asname=py_alias.loc, ref=impref, asname=asname
                )
            )
        return res

    def from_py_Import(self, py_imp: py_ast.Import) -> list[spy.ast.Import]:
        res = []
        for py_alias in py_imp.names:
            impref = ImportRef(py_alias.name, None)
            asname = py_alias.asname or py_alias.name
            res.append(
                spy.ast.Import(
                    loc=py_imp.loc, loc_asname=py_alias.loc, ref=impref, asname=asname
                )
            )
        return res

    # ====== spy.ast.Stmt ======

    def from_py_body(self, py_body: list[py_ast.stmt]) -> list[spy.ast.Stmt]:
        body: list[spy.ast.Stmt] = []
        for py_stmt in py_body:
            if isinstance(py_stmt, py_ast.AnnAssign):
                # special case, as it's the stmt wich generates two
                vardef, assign = self.from_py_AnnAssign(py_stmt)
                body.append(vardef)
                if assign:
                    body.append(assign)
            else:
                stmt = self.from_py_stmt(py_stmt)
                body.append(stmt)
        return body

    def from_py_stmt(self, py_node: py_ast.stmt) -> spy.ast.Stmt:
        return magic_dispatch(self, "from_py_stmt", py_node)

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

    def from_py_global_Assign(
        self, py_node: py_ast.Assign
    ) -> tuple[spy.ast.VarDef, spy.ast.Assign]:
        assign = self.from_py_stmt_Assign(py_node)
        assert isinstance(assign, spy.ast.Assign)
        kind: spy.ast.VarKind = "const"
        if py_node.targets[0].is_var:  # type: ignore
            kind = "var"
        vardef = spy.ast.VarDef(
            loc=py_node.loc,
            kind=kind,
            name=assign.target.value,
            type=spy.ast.Auto(loc=py_node.loc),
        )
        return vardef, assign

    def from_py_AnnAssign(
        self, py_node: py_ast.AnnAssign, is_global: bool = False
    ) -> tuple[spy.ast.VarDef, Optional[spy.ast.Assign]]:
        if not py_node.simple:
            self.error(
                f"not supported: assignments targets with parentheses",
                "this is not supported",
                py_node.target.loc,
            )
        # I don't think it's possible to generate an AnnAssign node with a
        # non-name target
        assert isinstance(py_node.target, py_ast.Name), "WTF?"

        # global VarDef are 'const' by default, unless you specify 'var'.
        # local VarDef are always 'var' (for now?)
        is_local = not is_global
        kind: spy.ast.VarKind
        if is_local or py_node.target.is_var:
            kind = "var"
        else:
            kind = "const"

        vardef = spy.ast.VarDef(
            loc=py_node.loc,
            kind=kind,
            name=py_node.target.id,
            type=self.from_py_expr(py_node.annotation),
        )

        if py_node.value is None:
            assign = None
        else:
            assign = spy.ast.Assign(
                loc=py_node.loc,
                target=spy.ast.StrConst(py_node.target.loc, py_node.target.id),
                value=self.from_py_expr(py_node.value),
            )

        return vardef, assign

    def from_py_stmt_Assign(self, py_node: py_ast.Assign) -> spy.ast.Stmt:
        # Assign can be pretty complex: it can have multiple targets, and a
        # target can be a Tuple or List in case of unpacking. For now, we
        # support only simple cases
        if len(py_node.targets) != 1:
            self.unsupported(py_node, "assign to multiple targets")
        py_target = py_node.targets[0]
        if isinstance(py_target, py_ast.Name):
            return spy.ast.Assign(
                loc=py_node.loc,
                target=spy.ast.StrConst(py_target.loc, py_target.id),
                value=self.from_py_expr(py_node.value),
            )
        elif isinstance(py_target, py_ast.Attribute):
            return spy.ast.SetAttr(
                loc=py_node.loc,
                target=self.from_py_expr(py_target.value),
                attr=spy.ast.StrConst(py_target.loc, py_target.attr),
                value=self.from_py_expr(py_node.value),
            )
        elif isinstance(py_target, py_ast.Subscript):
            target = self.from_py_expr(py_target.value)
            index = self.from_py_expr(py_target.slice)
            value = self.from_py_expr(py_node.value)
            if isinstance(index, spy.ast.Tuple):
                args = index.items
            else:
                args = [index]
            return spy.ast.SetItem(
                loc=py_node.loc,
                target=target,
                args=args,
                value=value,
            )
        elif isinstance(py_target, py_ast.Tuple):
            targets = []
            for item in py_target.elts:
                assert isinstance(item, py_ast.Name)
                targets.append(spy.ast.StrConst(item.loc, item.id))
            return spy.ast.UnpackAssign(
                loc=py_node.loc, targets=targets, value=self.from_py_expr(py_node.value)
            )
        else:
            self.unsupported(py_target, "assign to complex expressions")

    def from_py_stmt_AugAssign(self, py_node: py_ast.AugAssign) -> spy.ast.AugAssign:
        py_target = py_node.target
        if isinstance(py_target, py_ast.Name):
            opname = type(py_node.op).__name__
            op = self._binops[opname]
            return spy.ast.AugAssign(
                loc=py_node.loc,
                op=op,
                target=spy.ast.StrConst(py_target.loc, py_target.id),
                value=self.from_py_expr(py_node.value),
            )
        else:
            self.unsupported(py_target, "assign to complex expressions")

    def from_py_stmt_If(self, py_node: py_ast.If) -> spy.ast.If:
        return spy.ast.If(
            loc=py_node.loc,
            test=self.from_py_expr(py_node.test),
            then_body=self.from_py_body(py_node.body),
            else_body=self.from_py_body(py_node.orelse),
        )

    def from_py_stmt_While(self, py_node: py_ast.While) -> spy.ast.While:
        if py_node.orelse:
            self.unsupported(py_node, "`else` clause in `while` loops")
        return spy.ast.While(
            loc=py_node.loc,
            test=self.from_py_expr(py_node.test),
            body=self.from_py_body(py_node.body),
        )

    def from_py_stmt_For(self, py_node: py_ast.For) -> spy.ast.For:
        if py_node.orelse:
            # ideally, we would like to point to the 'else:' line, but we
            # cannot easiy get it from the ast. Too bad, let's point at the
            # 'for'.
            msg = "not implemented yet: `else` clause in `for` loops"
            forloc = py_node.loc.replace(
                line_end=py_node.loc.line_start, col_end=py_node.loc.col_start + 3
            )
            self.error(msg, "this is not supported", forloc)

        # Only support simple names as targets for now
        if not isinstance(py_node.target, py_ast.Name):
            self.unsupported(py_node.target, "complex for loop targets")

        seq = self.for_loop_seq
        self.for_loop_seq += 1
        return spy.ast.For(
            loc=py_node.loc,
            seq=seq,
            target=spy.ast.StrConst(py_node.target.loc, py_node.target.id),
            iter=self.from_py_expr(py_node.iter),
            body=self.from_py_body(py_node.body),
        )

    def from_py_stmt_Raise(self, py_node: py_ast.Raise) -> spy.ast.Raise:
        if py_node.cause:
            self.unsupported(py_node, "raise ... from ...")

        if py_node.exc is None:
            self.unsupported(py_node, "bare raise")

        exc = self.from_py_expr(py_node.exc)
        return spy.ast.Raise(loc=py_node.loc, exc=exc)

    def from_py_stmt_Assert(self, py_node: py_ast.Assert) -> spy.ast.Assert:
        test = self.from_py_expr(py_node.test)
        msg = self.from_py_expr(py_node.msg) if py_node.msg else None
        return spy.ast.Assert(py_node.loc, test, msg)

    def from_py_stmt_Break(self, py_node: py_ast.Break) -> spy.ast.Break:
        return spy.ast.Break(py_node.loc)

    def from_py_stmt_Continue(self, py_node: py_ast.Continue) -> spy.ast.Continue:
        return spy.ast.Continue(py_node.loc)

    # ====== spy.ast.Expr ======

    def from_py_expr(self, py_node: py_ast.expr) -> spy.ast.Expr:
        return magic_dispatch(self, "from_py_expr", py_node)

    from_py_expr_NotImplemented = unsupported

    def from_py_expr_Name(self, py_node: py_ast.Name) -> spy.ast.Name:
        return spy.ast.Name(py_node.loc, py_node.id)

    def from_py_expr_Constant(self, py_node: py_ast.Constant) -> spy.ast.Expr:
        # according to _ast.pyi, the type of const.value can be one of the
        # following:
        #     None, str, bytes, bool, int, float, complex, Ellipsis
        assert py_node.kind is None  # I don't know what is 'kind' here
        T = type(py_node.value)
        if T is str:
            return spy.ast.StrConst(py_node.loc, py_node.value)
        elif T in (int, float, bool, NoneType):
            return spy.ast.Constant(py_node.loc, py_node.value)
        elif T in (bytes, float, complex, Ellipsis):
            self.error(
                f"unsupported literal: {py_node.value!r}",
                f"this is not supported yet",
                py_node.loc,
            )
        else:
            assert False, f"Unexpected literal: {py_node.value}"

    def from_py_expr_Subscript(self, py_node: py_ast.Subscript) -> spy.ast.GetItem:
        value = self.from_py_expr(py_node.value)
        v = self.from_py_expr(py_node.slice)
        if isinstance(v, spy.ast.Tuple):
            args = v.items
        else:
            args = [v]
        return spy.ast.GetItem(py_node.loc, value, args)

    def from_py_expr_Attribute(self, py_node: py_ast.Attribute) -> spy.ast.GetAttr:
        value = self.from_py_expr(py_node.value)
        attr = spy.ast.StrConst(py_node.loc, py_node.attr)
        return spy.ast.GetAttr(py_node.loc, value, attr)

    def from_py_expr_List(self, py_node: py_ast.List) -> spy.ast.List:
        items = [self.from_py_expr(py_item) for py_item in py_node.elts]
        return spy.ast.List(py_node.loc, items)

    def from_py_expr_Tuple(self, py_node: py_ast.Tuple) -> spy.ast.Tuple:
        items = [self.from_py_expr(py_item) for py_item in py_node.elts]
        return spy.ast.Tuple(py_node.loc, items)

    _binops = {
        "Add": "+",
        "Sub": "-",
        "Mult": "*",
        "Div": "/",
        "FloorDiv": "//",
        "Mod": "%",
        "Pow": "**",
        "LShift": "<<",
        "RShift": ">>",
        "BitXor": "^",
        "BitOr": "|",
        "BitAnd": "&",
        "MatMult": "@",
    }

    _cmpops = {
        "Eq": "==",
        "NotEq": "!=",
        "Lt": "<",
        "LtE": "<=",
        "Gt": ">",
        "GtE": ">=",
        "Is": "is",
        "IsNot": "is not",
        "In": "in",
        "NotIn": "not in",
    }

    _unaryops = {
        "USub": "-",
        "UAdd": "+",
        "Invert": "~",
        "Not": "not",
    }

    def from_py_expr_BinOp(self, py_node: py_ast.BinOp) -> spy.ast.BinOp:
        opname = type(py_node.op).__name__
        op = self._binops[opname]
        left = self.from_py_expr(py_node.left)
        right = self.from_py_expr(py_node.right)
        return spy.ast.BinOp(py_node.loc, op, left, right)

    def from_py_expr_Compare(self, py_node: py_ast.Compare) -> spy.ast.CmpOp:
        if len(py_node.comparators) > 1:
            self.unsupported(py_node.comparators[1], "chained comparisons")
        opname = type(py_node.ops[0]).__name__
        op = self._cmpops[opname]
        left = self.from_py_expr(py_node.left)
        right = self.from_py_expr(py_node.comparators[0])
        return spy.ast.CmpOp(py_node.loc, op, left, right)

    def from_py_expr_UnaryOp(self, py_node: py_ast.UnaryOp) -> spy.ast.Expr:
        value = self.from_py_expr(py_node.operand)
        opname = type(py_node.op).__name__
        op = self._unaryops[opname]
        # special-case -NUM
        if (
            opname == "USub"
            and isinstance(value, spy.ast.Constant)
            and isinstance(value.value, (int, float))
        ):
            return spy.ast.Constant(value.loc, -value.value)
        return spy.ast.UnaryOp(py_node.loc, op, value)

    def from_py_expr_Call(
        self, py_node: py_ast.Call
    ) -> spy.ast.Call | spy.ast.CallMethod:
        if py_node.keywords:
            self.unsupported(py_node.keywords[0], "keyword arguments")
        func = self.from_py_expr(py_node.func)
        args = [self.from_py_expr(py_arg) for py_arg in py_node.args]
        if isinstance(func, spy.ast.GetAttr):
            return spy.ast.CallMethod(
                loc=py_node.loc, target=func.value, method=func.attr, args=args
            )
        else:
            return spy.ast.Call(loc=py_node.loc, func=func, args=args)

    def from_py_expr_BoolOp(
        self, py_node: py_ast.BoolOp
    ) -> typing.Union[spy.ast.And, spy.ast.Or]:
        values = [self.from_py_expr(value) for value in py_node.values]

        if isinstance(py_node.op, py_ast.And):
            return spy.ast.And(py_node.loc, values)
        elif isinstance(py_node.op, py_ast.Or):
            return spy.ast.Or(py_node.loc, values)
        else:
            self.unsupported(
                py_node.op, f"boolean operator {type(py_node.op).__name__}"
            )
