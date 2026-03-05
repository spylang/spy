import re
from typing import Literal, Optional, TypeGuard

from spy import ast
from spy.analyze.scope import SymTable
from spy.fqn import FQN
from spy.textbuilder import TextBuilder
from spy.util import magic_dispatch
from spy.vm.b import TYPES, B
from spy.vm.exc import W_Exception
from spy.vm.function import W_ASTFunc
from spy.vm.modules.__spy__.interp_list import W_InterpList
from spy.vm.object import W_Object, W_Type
from spy.vm.vm import SPyVM

FQN_FORMAT = Literal["full", "short"]

# Regex pattern for valid identifiers (alphanumeric + underscore)
VALID_IDENTIFIER = re.compile(r"^[a-zA-Z0-9_]+$")


class SPyBackend:
    """
    SPy backend: convert an AST back to SPy code.

    Mostly used for testing.
    """

    def __init__(self, vm: SPyVM, *, fqn_format: FQN_FORMAT = "short") -> None:
        self.vm = vm
        self.fqn_format = fqn_format
        self.out = TextBuilder(use_colors=False)
        self.w = self.out.w
        self.wl = self.out.wl
        # these are initialized by dump_w_func
        self.w_func: W_ASTFunc = None  # type: ignore
        self.vars_declared: set[str] = None  # type: ignore
        self.modname = ""  # set by dump_mod
        self.scope_stack: list[SymTable] = []

    def dump_mod(self, modname: str) -> str:
        """
        Dump the given module into human readable form.

        The main goal is to let humans to understand what happens during
        redshifting.

        1. "Aliased" functions: these are functions which are stored as
           e.g. `mod.foo` but actually point to a function with a different
           FQN.

        2. All the PBCs which are contained in the module namespace. This
           includes module-level functions and types, but also any other PBC
           which was generated inside a blue closure.
        """
        self.modname = modname

        # part 1: aliases
        w_mod = self.vm.modules_w[modname]
        for attr, w_obj in w_mod.items_w():
            expected_fqn = FQN(modname).join(attr)
            if (
                isinstance(w_obj, W_ASTFunc)
                and w_obj.color == "red"
                and w_obj.fqn != expected_fqn
            ):
                self.out.wl(f"{attr} = `{w_obj.fqn}`")
        self.out.wl()

        # part 2: all the other FQNs
        for fqn, w_obj in self.vm.fqns_by_modname(modname):
            if (
                isinstance(w_obj, W_ASTFunc)
                and w_obj.color == "red"
                and w_obj.fqn == fqn
            ):
                self.dump_w_func(fqn, w_obj)
                self.out.wl()

        return self.out.build()

    def is_module_global(self, fqn: FQN) -> bool:
        return (
            len(fqn.parts) == 2
            and fqn.modname == self.modname
            and fqn.parts[-1].suffix == ""
        )

    def dump_w_func(self, fqn: FQN, w_func: W_ASTFunc) -> None:
        if self.fqn_format == "short" and self.is_module_global(fqn):
            # display 'def foo()' instead of 'def `test::foo`()', if possible
            name = fqn.symbol_name
        else:
            name = self.fmt_fqn(fqn)
        self.w_func = w_func
        self.vars_declared = set()
        w_functype = w_func.w_functype
        params = self.fmt_params(w_func)
        if w_functype.w_restype is TYPES.w_NoneType and self.fqn_format == "short":
            ret = "None"  # special case: emit '-> None' instead of '-> NoneType'
        else:
            ret = self.fmt_w_obj(w_functype.w_restype)
        self.scope_stack.append(w_func.funcdef.symtable)
        self.wl(f"def {name}({params}) -> {ret}:")
        with self.out.indent():
            for stmt in w_func.funcdef.body:
                self.emit_stmt(stmt)
        self.scope_stack.pop()

    def fmt_params(self, w_func: W_ASTFunc) -> str:
        funcdef = w_func.funcdef
        l = []
        for i, param in enumerate(w_func.w_functype.params):
            n = funcdef.args[i].name
            t = self.fmt_w_obj(param.w_T)
            if param.kind == "simple":
                l.append(f"{n}: {t}")
            elif param.kind == "var_positional":
                assert i == len(funcdef.args) - 1
                l.append(f"*{n}: {t}")
            else:
                assert False
        return ", ".join(l)

    def fmt_w_obj(self, w_obj: W_Object) -> str:
        if isinstance(w_obj, W_Type) and issubclass(w_obj.pyclass, W_InterpList):
            # this is a ugly special case for now, we need to find a better
            # solution
            return w_obj.fqn.human_name
        #
        # this assumes that w_obj has a valid FQN
        fqn = self.vm.reverse_lookup_global(w_obj)
        assert fqn is not None
        return self.fmt_fqn(fqn)

    def fmt_fqn(self, fqn: FQN) -> str:
        if self.fqn_format == "full":
            name = str(fqn)
        elif self.fqn_format == "short":
            name = fqn.human_name  # don't show builtins::
        else:
            assert False
        #
        if VALID_IDENTIFIER.match(name):
            return name
        else:
            return f"`{name}`"

    # ==============

    def emit_decl(self, decl: ast.Decl) -> None:
        magic_dispatch(self, "emit_decl", decl)

    def emit_stmt(self, stmt: ast.Stmt) -> None:
        magic_dispatch(self, "emit_stmt", stmt)

    def fmt_expr(self, expr: ast.Expr) -> str:
        return magic_dispatch(self, "fmt_expr", expr)

    # declarations

    def emit_decl_GlobalFuncDef(self, decl: ast.GlobalFuncDef) -> None:
        self.emit_stmt(decl.funcdef)

    # statements

    def emit_declare_var_maybe(self, varname: str) -> None:
        symtable = self.scope_stack[-1]
        sym = symtable.lookup(varname)
        if (
            self.w_func.redshifted
            and sym.level == 0
            and varname not in self.vars_declared
        ):
            assert self.w_func.locals_types_w is not None
            w_T = self.w_func.locals_types_w[varname]
            t = self.fmt_w_obj(w_T)
            self.wl(f"{varname}: {t}")
            self.vars_declared.add(varname)

    def emit_stmt_FuncDef(self, funcdef: ast.FuncDef) -> None:
        name = funcdef.name
        paramlist = []
        for funcarg in funcdef.args:
            n = funcarg.name
            t = self.fmt_expr(funcarg.type)
            paramlist.append(f"{n}: {t}")
        params = ", ".join(paramlist)
        ret = self.fmt_expr(funcdef.return_type)
        self.scope_stack.append(funcdef.symtable)
        self.wl(f"def {name}({params}) -> {ret}:")
        with self.out.indent():
            for stmt in funcdef.body:
                self.emit_stmt(stmt)
        self.scope_stack.pop()

    def emit_stmt_ClassDef(self, classdef: ast.ClassDef) -> None:
        assert classdef.kind == "struct", "IMPLEMENT ME"
        name = classdef.name
        self.scope_stack.append(classdef.symtable)
        self.wl("@struct")
        self.wl(f"class {name}:")
        with self.out.indent():
            for stmt in classdef.body:
                self.emit_stmt(stmt)
        self.scope_stack.pop()

    def emit_stmt_Pass(self, stmt: ast.Pass) -> None:
        self.wl("pass")

    def emit_stmt_Break(self, stmt: ast.Break) -> None:
        self.wl("break")

    def emit_stmt_Continue(self, stmt: ast.Continue) -> None:
        self.wl("continue")

    def emit_stmt_Return(self, ret: ast.Return) -> None:
        v = self.fmt_expr(ret.value)
        self.wl(f"return {v}")

    def emit_stmt_Assign(self, assign: ast.Assign) -> None:
        varname = assign.target.value
        self.emit_declare_var_maybe(varname)
        v = self.fmt_expr(assign.value)
        self.wl(f"{varname} = {v}")

    def emit_stmt_AssignLocal(self, assign: ast.AssignLocal) -> None:
        varname = assign.target.value
        self.emit_declare_var_maybe(varname)
        v = self.fmt_expr(assign.value)
        self.wl(f"{varname} = {v}")

    def emit_stmt_AssignCell(self, assign: ast.AssignCell) -> None:
        varname = self.fmt_fqn(assign.target_fqn)
        v = self.fmt_expr(assign.value)
        self.wl(f"{varname} = {v}")

    def emit_stmt_AugAssign(self, node: ast.AugAssign) -> None:
        varname = node.target.value
        op = node.op
        v = self.fmt_expr(node.value)
        self.wl(f"{varname} {op}= {v}")

    def emit_stmt_UnpackAssign(self, unpack: ast.UnpackAssign) -> None:
        targets = ", ".join([t.value for t in unpack.targets])
        v = self.fmt_expr(unpack.value)
        self.wl(f"{targets} = {v}")

    def emit_stmt_SetAttr(self, node: ast.SetAttr) -> None:
        t = self.fmt_expr(node.target)
        a = node.attr.value
        v = self.fmt_expr(node.value)
        self.wl(f"{t}.{a} = {v}")

    def emit_stmt_SetItem(self, node: ast.SetItem) -> None:
        t = self.fmt_expr(node.target)
        arglist = [self.fmt_expr(arg) for arg in node.args]
        args = ", ".join(arglist)
        v = self.fmt_expr(node.value)
        self.wl(f"{t}[{args}] = {v}")

    def emit_stmt_VarDef(self, vardef: ast.VarDef) -> None:
        varname = vardef.name.value
        is_auto = isinstance(vardef.type, ast.Auto)
        if is_auto:
            assert vardef.value
            v = self.fmt_expr(vardef.value)
            self.wl(f"{varname} = {v}")
        else:
            t = self.fmt_expr(vardef.type)
            if vardef.value:
                v = self.fmt_expr(vardef.value)
                self.wl(f"{varname}: {t} = {v}")
            else:
                self.wl(f"{varname}: {t}")
        self.vars_declared.add(varname)

    def emit_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> None:
        v = self.fmt_expr(stmt.value)
        self.wl(f"{v}")

    def emit_stmt_While(self, while_node: ast.While) -> None:
        test = self.fmt_expr(while_node.test)
        self.wl(f"while {test}:")
        with self.out.indent():
            for stmt in while_node.body:
                self.emit_stmt(stmt)

    def emit_stmt_For(self, for_node: ast.For) -> None:
        target = for_node.target.value
        iter_expr = self.fmt_expr(for_node.iter)
        self.wl(f"for {target} in {iter_expr}:")
        with self.out.indent():
            for stmt in for_node.body:
                self.emit_stmt(stmt)

    def emit_stmt_If(self, if_node: ast.If) -> None:
        test = self.fmt_expr(if_node.test)
        self.wl(f"if {test}:")
        with self.out.indent():
            for stmt in if_node.then_body:
                self.emit_stmt(stmt)
        if if_node.else_body:
            self.wl("else:")
            with self.out.indent():
                for stmt in if_node.else_body:
                    self.emit_stmt(stmt)

    def emit_stmt_Raise(self, raise_node: ast.Raise) -> None:
        exc = self.fmt_expr(raise_node.exc)
        self.wl(f"raise {exc}")

    def emit_stmt_Assert(self, assert_node: ast.Assert) -> None:
        test = self.fmt_expr(assert_node.test)

        if assert_node.msg is not None:
            msg = self.fmt_expr(assert_node.msg)
            self.wl(f"assert {test}, {msg}")
        else:
            self.wl(f"assert {test}")

    # expressions

    def fmt_expr_Constant(self, const: ast.Constant) -> str:
        return repr(const.value)

    def fmt_expr_StrConst(self, const: ast.StrConst) -> str:
        return repr(const.value)

    def fmt_expr_FQNConst(self, const: ast.FQNConst) -> str:
        # hack hack hack: in case of prebuilt exceptions, let's emit a more
        # readable form. This is needed because for now raise supports only
        # blue exceptions, and so all of them are turned into FQNConst.
        w_val = self.vm.lookup_global(const.fqn)
        if isinstance(w_val, W_Exception):
            t = self.vm.dynamic_type(w_val).fqn.symbol_name  # e.g. 'Exception'
            m = w_val.message
            return f"{t}({m!r})"
        return self.fmt_fqn(const.fqn)

    def fmt_expr_LocConst(self, const: ast.LocConst) -> str:
        r = const.value._repr()
        return f"Loc('{r}')"

    def fmt_expr_Name(self, name: ast.Name) -> str:
        return name.id

    def fmt_expr_NameLocalDirect(self, name: ast.NameLocalDirect) -> str:
        return name.sym.name

    def fmt_expr_NameOuterCell(self, name: ast.NameOuterCell) -> str:
        return self.fmt_fqn(name.fqn)

    def fmt_expr_BinOp(self, binop: ast.BinOp) -> str:
        l = self.fmt_expr(binop.left)
        r = self.fmt_expr(binop.right)
        if binop.left.precedence < binop.precedence:
            l = f"({l})"
        if binop.right.precedence < binop.precedence:
            r = f"({r})"
        return f"{l} {binop.op} {r}"

    def fmt_expr_CmpOp(self, op: ast.CmpOp) -> str:
        l = self.fmt_expr(op.left)
        r = self.fmt_expr(op.right)
        if op.left.precedence < op.precedence:
            l = f"({l})"
        if op.right.precedence < op.precedence:
            r = f"({r})"
        return f"{l} {op.op} {r}"

    def fmt_expr_And(self, op: ast.And) -> str:
        l = self.fmt_expr(op.left)
        r = self.fmt_expr(op.right)
        if op.left.precedence < op.precedence:
            l = f"({l})"
        if op.right.precedence < op.precedence:
            r = f"({r})"
        return f"{l} and {r}"

    def fmt_expr_Or(self, op: ast.Or) -> str:
        l = self.fmt_expr(op.left)
        r = self.fmt_expr(op.right)
        if op.left.precedence < op.precedence:
            l = f"({l})"
        if op.right.precedence < op.precedence:
            r = f"({r})"
        return f"{l} or {r}"

    def fmt_expr_UnaryOp(self, unary: ast.UnaryOp) -> str:
        v = self.fmt_expr(unary.value)
        if unary.value.precedence < unary.precedence:
            v = f"({v})"
        return f"{unary.op}{v}"

    def fmt_expr_AssignExpr(self, assignexpr: ast.AssignExpr) -> str:
        return self._fmt_assignexpr(
            assignexpr.target.value, assignexpr.value, assignexpr.precedence
        )

    def fmt_expr_AssignExprLocal(self, assignexpr: ast.AssignExprLocal) -> str:
        return self._fmt_assignexpr(
            assignexpr.target.value, assignexpr.value, assignexpr.precedence
        )

    def fmt_expr_AssignExprCell(self, assignexpr: ast.AssignExprCell) -> str:
        target = self.fmt_fqn(assignexpr.target_fqn)
        return self._fmt_assignexpr(target, assignexpr.value, assignexpr.precedence)

    def _fmt_assignexpr(
        self, target: str, value_expr: ast.Expr, precedence: int
    ) -> str:
        value = self.fmt_expr(value_expr)
        if value_expr.precedence < precedence:
            value = f"({value})"
        return f"{target} := {value}"

    # special cases
    FQN2BinOp = {
        FQN("operator::i32_add"): "+",
        FQN("operator::i32_sub"): "-",
        FQN("operator::i32_mul"): "*",
        FQN("operator::i32_div"): "/",
        FQN("operator::i32_floordiv"): "//",
        FQN("operator::f64_add"): "+",
        FQN("operator::f64_sub"): "-",
        FQN("operator::f64_mul"): "*",
        FQN("operator::f64_div"): "/",
        FQN("operator::f64_floordiv"): "//",
    }

    FQN2CmpOp = {
        FQN("operator::i32_eq"): "==",
        FQN("operator::i32_ne"): "!=",
        FQN("operator::i32_lt"): "<",
        FQN("operator::i32_le"): "<=",
        FQN("operator::i32_gt"): ">",
        FQN("operator::i32_ge"): ">=",
        FQN("operator::f64_eq"): "==",
        FQN("operator::f64_ne"): "!=",
        FQN("operator::f64_lt"): "<",
        FQN("operator::f64_le"): "<=",
        FQN("operator::f64_gt"): ">",
        FQN("operator::f64_ge"): ">=",
    }

    def pprint_call_maybe(self, call: ast.Call) -> Optional[str]:
        if not isinstance(call.func, ast.FQNConst):
            # don't pretty print
            return None
        fqn = call.func.fqn

        if fqn in self.FQN2BinOp:
            # `operator::i32_add`(a, b) --> "a + b"
            assert len(call.args) == 2
            op = self.FQN2BinOp[fqn]
            binop = ast.BinOp(call.loc, op, call.args[0], call.args[1])
            return self.fmt_expr_BinOp(binop)
        elif fqn in self.FQN2CmpOp:
            assert len(call.args) == 2
            op = self.FQN2CmpOp[fqn]
            cmpop = ast.CmpOp(call.loc, op, call.args[0], call.args[1])
            return self.fmt_expr_CmpOp(cmpop)
        elif fqn == FQN("operator::raise"):
            # `operator::raise('TypeError', ...)` -->."raise TypeError(...)"
            assert len(call.args) == 4
            etype, msg, fname, lineno = call.args
            assert isinstance(etype, ast.StrConst)
            assert isinstance(msg, ast.StrConst)
            assert isinstance(fname, ast.StrConst)
            assert isinstance(lineno, ast.Constant)
            E = etype.value
            m = self.fmt_expr(msg)
            # show only the last part of the filename
            f = fname.value.split("/")[-1]
            l = lineno.value
            if m == "''":
                return f"raise {etype.value} # /.../{f}:{l}"
            else:
                return f"raise {etype.value}({m}) # /.../{f}:{l}"
        return None

    def fmt_expr_Call(self, call: ast.Call) -> str:
        if self.fqn_format == "short" and (res := self.pprint_call_maybe(call)):
            # pretty print
            return res
        else:
            # standard case
            name = self.fmt_expr(call.func)
            arglist = [self.fmt_expr(arg) for arg in call.args]
            args = ", ".join(arglist)
            return f"{name}({args})"

    def fmt_expr_CallMethod(self, callm: ast.CallMethod) -> str:
        t = self.fmt_expr(callm.target)
        m = callm.method.value
        arglist = [self.fmt_expr(arg) for arg in callm.args]
        args = ", ".join(arglist)
        return f"{t}.{m}({args})"

    def fmt_expr_GetItem(self, getitem: ast.GetItem) -> str:
        v = self.fmt_expr(getitem.value)
        arglist = [self.fmt_expr(arg) for arg in getitem.args]
        args = ", ".join(arglist)
        return f"{v}[{args}]"

    def fmt_expr_GetAttr(self, node: ast.GetAttr) -> str:
        v = self.fmt_expr(node.value)
        return f"{v}.{node.attr.value}"

    def fmt_expr_List(self, node: ast.List) -> str:
        itemlist = [self.fmt_expr(it) for it in node.items]
        items = ", ".join(itemlist)
        return f"[{items}]"

    def fmt_expr_Tuple(self, node: ast.Tuple) -> str:
        itemlist = [self.fmt_expr(it) for it in node.items]
        items = ", ".join(itemlist)
        return f"({items})"

    def fmt_expr_Slice(self, node: ast.Slice) -> str:
        (start, stop, step) = [
            self.fmt_expr(exp) for exp in (node.start, node.stop, node.step)
        ]

        def hide_none(val: str) -> str:
            return val if val != "None" else ""

        return f"{hide_none(start)}:{hide_none(stop)}{f':{step}' if hide_none(step) else ''}"

    def fmt_expr_Dict(self, node: ast.Dict) -> str:
        pairs = [
            f"{self.fmt_expr(kv.key)}: {self.fmt_expr(kv.value)}" for kv in node.items
        ]
        return "{" + ", ".join(pairs) + "}"
