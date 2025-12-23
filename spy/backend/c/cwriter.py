from types import NoneType
from typing import TYPE_CHECKING

from spy import ast
from spy.backend.c import c_ast as C
from spy.backend.c.context import C_Ident, Context
from spy.fqn import FQN
from spy.location import Loc
from spy.textbuilder import TextBuilder
from spy.util import magic_dispatch, shortrepr
from spy.vm.b import TYPES, B
from spy.vm.builtin import IRTag
from spy.vm.function import W_ASTFunc, W_Func
from spy.vm.modules.unsafe.ptr import W_Ptr

if TYPE_CHECKING:
    from spy.backend.c.cmodwriter import CModuleWriter


class CFuncWriter:
    ctx: Context
    cmodw: "CModuleWriter"
    tbc: TextBuilder
    fqn: FQN
    w_func: W_ASTFunc
    last_emitted_linenos: tuple[int, int]

    def __init__(
        self, ctx: Context, cmodw: "CModuleWriter", fqn: FQN, w_func: W_ASTFunc
    ) -> None:
        self.ctx = ctx
        self.cmodw = cmodw
        self.tbc = cmodw.tbc
        self.fqn = fqn
        self.w_func = w_func
        self.last_emitted_linenos = (-1, -1)  # see emit_lineno_maybe

    def ppc(self) -> None:
        """
        Pretty print the C code generated so far
        """
        print(self.tbc.build())

    def ppast(self) -> None:
        """
        Pretty print the AST
        """
        self.w_func.funcdef.pp()

    def emit(self) -> None:
        """
        Emit the code for the whole function
        """
        self.emit_lineno(self.w_func.funcdef.loc.line_start)
        c_func = self.ctx.c_function(self.fqn.c_name, self.w_func)
        self.tbc.wl(c_func.decl() + " {")
        with self.tbc.indent():
            self.emit_local_vars()
            for stmt in self.w_func.funcdef.body:
                self.emit_stmt(stmt)

            if self.w_func.w_functype.w_restype is not TYPES.w_NoneType:
                # this is a non-void function: if we arrive here, it means we
                # reached the end of the function without a return. Ideally,
                # we would like to also report an error message, but for now
                # we just abort.
                msg = "reached the end of the function without a `return`"
                self.tbc.wl(f"abort(); /* {msg} */")
        self.tbc.wl("}")

    def emit_local_vars(self) -> None:
        """
        Declare all local variables.

        We need to declare all of them in advance because C scoping rules are
        different than SPy scoping rules, so we emit the C declaration when we
        see e.g. a VarDef.
        """
        assert self.w_func.locals_types_w is not None
        param_names = [arg.name for arg in self.w_func.funcdef.args]
        for varname, w_T in self.w_func.locals_types_w.items():
            c_type = self.ctx.w2c(w_T)
            if (
                varname not in ("@return", "@if", "@and", "@or", "@while", "@assert")
                and varname not in param_names
            ):
                c_varname = C_Ident(varname)
                self.tbc.wl(f"{c_type} {c_varname};")

    # ==============

    def emit_lineno_maybe(self, loc: Loc) -> None:
        """
        Emit a #line directive, but only if it's needed.
        """
        # line numbers corresponding to the last emitted #line
        last_spy, last_c = self.last_emitted_linenos
        #
        # line numbers as they are understood by the C compiler, i.e. what
        # goes to debuginfo if we don't emit a new #line
        cur_c = self.tbc.lineno
        cur_spy = last_spy + (cur_c - last_c) - 1
        #
        # desired spy line number, i.e. what we would like it to be
        desired_spy = loc.line_start
        if desired_spy != cur_spy:
            # time to emit a new #line directive
            self.emit_lineno(desired_spy)

    def emit_lineno(self, spyline: int) -> None:
        """
        Emit a #line directive, unconditionally
        """
        if self.cmodw.c_mod.spyfile is None:
            # we don't have an associated spyfile, so we cannot emit SPY_LINE
            return
        cline = self.tbc.lineno
        self.tbc.wl(f"#line SPY_LINE({spyline}, {cline})")
        self.last_emitted_linenos = (spyline, cline)

    def emit_stmt(self, stmt: ast.Stmt) -> None:
        self.emit_lineno_maybe(stmt.loc)
        magic_dispatch(self, "emit_stmt", stmt)

    def fmt_expr(self, expr: ast.Expr) -> C.Expr:
        # XXX: here we should probably handle typeconv, if present.
        # However, we cannot yet write a test for it because:
        #   - we cannot test DynamicCast because we don't support object
        #   - we cannot test NumericConv because the expressions are
        #     automatically converted by the C compiler anyway
        return magic_dispatch(self, "fmt_expr", expr)

    # ===== statements =====

    def emit_stmt_Pass(self, stmt: ast.Pass) -> None:
        pass

    def emit_stmt_Break(self, stmt: ast.Break) -> None:
        self.tbc.wl("break;")

    def emit_stmt_Continue(self, stmt: ast.Continue) -> None:
        self.tbc.wl("continue;")

    def emit_stmt_Return(self, ret: ast.Return) -> None:
        v = self.fmt_expr(ret.value)
        if v is C.Void():
            self.tbc.wl("return;")
        else:
            self.tbc.wl(f"return {v};")

    def emit_stmt_VarDef(self, vardef: ast.VarDef) -> None:
        # NOTE: the local variable declaration happens in emit_local_vars, here we just
        # assign the value
        if vardef.value:
            target = vardef.name.value
            v = self.fmt_expr(vardef.value)
            self.tbc.wl(f"{target} = {v};")

    def emit_stmt_Assign(self, assign: ast.Assign) -> None:
        assert False, "ast.Assign nodes should not survive redshifting"

    def emit_stmt_AssignLocal(self, assign: ast.AssignLocal) -> None:
        target = assign.target.value
        v = self.fmt_expr(assign.value)
        c_varname = C_Ident(target)
        self.tbc.wl(f"{c_varname} = {v};")

    def emit_stmt_AssignCell(self, assign: ast.AssignCell) -> None:
        v = self.fmt_expr(assign.value)
        target = assign.target_fqn.c_name
        c_varname = C_Ident(target)
        self.tbc.wl(f"{c_varname} = {v};")

    def emit_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> None:
        v = self.fmt_expr(stmt.value)
        if v is C.Void():
            pass
        else:
            self.tbc.wl(f"{v};")

    def emit_stmt_If(self, if_node: ast.If) -> None:
        test = self.fmt_expr(if_node.test)
        self.tbc.wl(f"if ({test})" + "{")
        with self.tbc.indent():
            for stmt in if_node.then_body:
                self.emit_stmt(stmt)
        #
        if if_node.else_body:
            self.tbc.wl("} else {")
            with self.tbc.indent():
                for stmt in if_node.else_body:
                    self.emit_stmt(stmt)
        #
        self.tbc.wl("}")

    def emit_stmt_While(self, while_node: ast.While) -> None:
        test = self.fmt_expr(while_node.test)
        self.tbc.wl(f"while ({test}) " + "{")
        with self.tbc.indent():
            for stmt in while_node.body:
                self.emit_stmt(stmt)
        self.tbc.wl("}")

    def emit_stmt_Assert(self, assert_node: ast.Assert) -> None:
        test = self.fmt_expr(assert_node.test)
        self.tbc.wl(f"if (!({test}))" + " {")
        with self.tbc.indent():
            if assert_node.msg is not None:
                # TODO: assuming msg is always a string. extend the logic to work with other types
                msg = self.fmt_expr(assert_node.msg)
                self.tbc.wl(
                    f'spy_panic("AssertionError", ({msg})->utf8, '
                    f'"{assert_node.loc.filename}", {assert_node.loc.line_start});'
                )
            else:
                self.tbc.wl(
                    f'spy_panic("AssertionError", "assertion failed", '
                    f'"{assert_node.loc.filename}", {assert_node.loc.line_start});'
                )

        self.tbc.wl("}")

    # ===== expressions =====

    def fmt_expr_Constant(self, const: ast.Constant) -> C.Expr:
        # unsupported literals are rejected directly by the parser, see
        # Parser.from_py_expr_Constant
        T = type(const.value)
        assert T in (int, float, bool, str, NoneType)
        if T is NoneType:
            return C.Void()
        elif T is int:
            return C.Literal(str(const.value))
        elif T is float:
            return C.Literal(str(const.value))
        elif T is bool:
            return C.Literal(str(const.value).lower())
        else:
            raise NotImplementedError("WIP")

    def fmt_expr_StrConst(self, const: ast.StrConst) -> C.Expr:
        # SPy string literals must be initialized as C globals. We want to
        # generate the following:
        #
        #     // global declarations
        #     static spy_Str SPY_g_str0 = {5, "hello"};
        #     ...
        #     // literal expr
        #     &SPY_g_str0 /* "hello" */
        #
        # Note that in the literal expr we also put a comment showing what is
        # the content of the literal: hopefully this will make the code more
        # readable for humans.
        #
        # Emit the global decl
        s = const.value
        utf8 = s.encode("utf-8")
        v = self.cmodw.new_global_var("str")  # SPY_g_str0
        n = len(utf8)
        lit = C.Literal.from_bytes(utf8)
        init = "{%d, %s}" % (n, lit)
        self.cmodw.tbc_globals.wl(f"static spy_Str {v} = {init};")
        #
        # shortstr is what we show in the comment, with a length limit
        comment = shortrepr(utf8.decode("utf-8"), 15)
        v = f"{v} /* {comment} */"
        return C.UnaryOp("&", C.Literal(v))

    def fmt_expr_FQNConst(self, const: ast.FQNConst) -> C.Expr:
        w_obj = self.ctx.vm.lookup_global(const.fqn)
        if isinstance(w_obj, W_Ptr):
            # for each PtrType, we emit the corresponding NULL define with the
            # appropriate fqn name, see Context.new_ptr_type
            assert w_obj.addr == 0, "only NULL ptrs can be constants"
            return C.Literal(const.fqn.c_name)
        elif isinstance(w_obj, W_Func):
            return C.Literal(const.fqn.c_name)
        else:
            assert False

    def fmt_expr_Name(self, name: ast.Name) -> C.Expr:
        assert False, "ast.Name nodes should not survive redshifting"

    def fmt_expr_NameLocal(self, name: ast.NameLocal) -> C.Expr:
        varname = C_Ident(name.sym.name)
        return C.Literal(f"{varname}")

    def fmt_expr_NameOuterCell(self, name: ast.NameOuterCell) -> C.Expr:
        return C.Literal(name.fqn.c_name)

    def fmt_expr_NameOuterDirect(self, name: ast.NameOuterDirect) -> C.Expr:
        # at the moment of writing, closed-over variables are always blue, so
        # they should not survive redshifting
        assert False, "unexepcted NameOuterDirect"

    def fmt_expr_AssignExpr(self, assignexpr: ast.AssignExpr) -> C.Expr:
        return self._fmt_assignexpr(assignexpr.target.value, assignexpr.value)

    def fmt_expr_AssignExprLocal(self, assignexpr: ast.AssignExprLocal) -> C.Expr:
        return self._fmt_assignexpr(assignexpr.target.value, assignexpr.value)

    def fmt_expr_AssignExprCell(self, assignexpr: ast.AssignExprCell) -> C.Expr:
        return self._fmt_assignexpr(assignexpr.target_fqn.c_name, assignexpr.value)

    def _fmt_assignexpr(self, target: str, value_expr: ast.Expr) -> C.Expr:
        target_lit = C.Literal(target)
        value = self.fmt_expr(value_expr)
        return C.BinOp("=", target_lit, value)

    def fmt_expr_BinOp(self, binop: ast.BinOp) -> C.Expr:
        raise NotImplementedError(
            "ast.BinOp not supported. It should have been redshifted away"
        )

    def fmt_expr_And(self, op: ast.And) -> C.Expr:
        l = self.fmt_expr(op.left)
        r = self.fmt_expr(op.right)
        return C.BinOp("&&", l, r)

    def fmt_expr_Or(self, op: ast.Or) -> C.Expr:
        l = self.fmt_expr(op.left)
        r = self.fmt_expr(op.right)
        return C.BinOp("||", l, r)

    FQN2BinOp = {
        FQN("operator::i8_add"): "+",
        FQN("operator::i8_sub"): "-",
        FQN("operator::i8_mul"): "*",
        FQN("operator::i8_lshift"): "<<",
        FQN("operator::i8_rshift"): ">>",
        FQN("operator::i8_and"): "&",
        FQN("operator::i8_or"): "|",
        FQN("operator::i8_xor"): "^",
        FQN("operator::i8_eq"): "==",
        FQN("operator::i8_ne"): "!=",
        FQN("operator::i8_lt"): "<",
        FQN("operator::i8_le"): "<=",
        FQN("operator::i8_gt"): ">",
        FQN("operator::i8_ge"): ">=",
        #
        FQN("operator::u8_add"): "+",
        FQN("operator::u8_sub"): "-",
        FQN("operator::u8_mul"): "*",
        FQN("operator::u8_lshift"): "<<",
        FQN("operator::u8_rshift"): ">>",
        FQN("operator::u8_and"): "&",
        FQN("operator::u8_or"): "|",
        FQN("operator::u8_xor"): "^",
        FQN("operator::u8_eq"): "==",
        FQN("operator::u8_ne"): "!=",
        FQN("operator::u8_lt"): "<",
        FQN("operator::u8_le"): "<=",
        FQN("operator::u8_gt"): ">",
        FQN("operator::u8_ge"): ">=",
        #
        FQN("operator::i32_add"): "+",
        FQN("operator::i32_sub"): "-",
        FQN("operator::i32_mul"): "*",
        FQN("operator::i32_lshift"): "<<",
        FQN("operator::i32_rshift"): ">>",
        FQN("operator::i32_and"): "&",
        FQN("operator::i32_or"): "|",
        FQN("operator::i32_xor"): "^",
        FQN("operator::i32_eq"): "==",
        FQN("operator::i32_ne"): "!=",
        FQN("operator::i32_lt"): "<",
        FQN("operator::i32_le"): "<=",
        FQN("operator::i32_gt"): ">",
        FQN("operator::i32_ge"): ">=",
        #
        FQN("operator::u32_add"): "+",
        FQN("operator::u32_sub"): "-",
        FQN("operator::u32_mul"): "*",
        FQN("operator::u32_lshift"): "<<",
        FQN("operator::u32_rshift"): ">>",
        FQN("operator::u32_and"): "&",
        FQN("operator::u32_or"): "|",
        FQN("operator::u32_xor"): "^",
        FQN("operator::u32_eq"): "==",
        FQN("operator::u32_ne"): "!=",
        FQN("operator::u32_lt"): "<",
        FQN("operator::u32_le"): "<=",
        FQN("operator::u32_gt"): ">",
        FQN("operator::u32_ge"): ">=",
        #
        FQN("operator::f64_add"): "+",
        FQN("operator::f64_sub"): "-",
        FQN("unsafe::f64_ieee754_div"): "/",
        FQN("operator::f64_mul"): "*",
        FQN("operator::f64_eq"): "==",
        FQN("operator::f64_ne"): "!=",
        FQN("operator::f64_lt"): "<",
        FQN("operator::f64_le"): "<=",
        FQN("operator::f64_gt"): ">",
        FQN("operator::f64_ge"): ">=",
        # the following are NOT special cased, and are implemented in
        # operator.h. They are listed here to make emphasize that they are not
        # omitted from above by mistake:
        # T is any of the following types: i8, u8, i32, u32 and f64
        # FQN('operator::T_div')
        # FQN('operator::T_floordiv')
        # FQN('operator::T_mod')
        # FQN('unsafe::T_unchecked_div')
        # FQN('unsafe::T_unchecked_floordiv')
        # FQN('unsafe::T_unchecked_mod')
    }

    FQN2UnaryOp = {
        FQN("operator::i8_neg"): "-",
        FQN("operator::i32_neg"): "-",
        FQN("operator::f64_neg"): "-",
    }

    def fmt_expr_Call(self, call: ast.Call) -> C.Expr:
        assert isinstance(call.func, ast.FQNConst), (
            "indirect calls are not supported yet"
        )
        fqn = call.func.fqn

        irtag = self.ctx.vm.get_irtag(fqn)
        if call.func.fqn.modname == "jsffi":
            self.cmodw.emit_jsffi_error_maybe()

        if op := self.FQN2BinOp.get(fqn):
            # binop special case
            assert len(call.args) == 2
            l, r = [self.fmt_expr(arg) for arg in call.args]
            return C.BinOp(op, l, r)

        elif op := self.FQN2UnaryOp.get(fqn):
            # unary op special case
            assert len(call.args) == 1
            v = self.fmt_expr(call.args[0])
            return C.UnaryOp(op, v)

        elif irtag.tag == "struct.make":
            return self.fmt_struct_make(fqn, call, irtag)

        elif irtag.tag == "struct.getfield":
            return self.fmt_struct_getfield(fqn, call, irtag)

        elif irtag.tag == "ptr.getfield":
            return self.fmt_ptr_getfield(fqn, call, irtag)

        elif irtag.tag == "ptr.setfield":
            return self.fmt_ptr_setfield(fqn, call)

        elif irtag.tag == "ptr.deref":
            # this is not strictly necessary as it's just a generic call, but
            # we handle ptr.deref explicitly for extra clarity
            return self.fmt_generic_call(fqn, call)

        elif irtag.tag in ("ptr.getitem", "ptr.store"):
            # see unsafe/ptr.py::w_GETITEM and w_SETITEM there, we insert an
            # extra "w_loc" argument, which is not needed by the C backend
            # because we rely on C's own mechanism to get line numbers.
            # Moreover, we don't have a way to render "W_Loc" consts to C.
            #
            # So, we just remove the last arguments. Note that this much match
            # with the signature of the load/store functions generated by
            # unsafe.h:SPY_PTR_FUNCTIONS.
            assert isinstance(call.args[-1], ast.LocConst)
            call.args.pop()  # remove it
            return self.fmt_generic_call(fqn, call)

        else:
            return self.fmt_generic_call(fqn, call)

    def fmt_generic_call(self, fqn: FQN, call: ast.Call) -> C.Expr:
        # default case: call a function with the corresponding name
        self.ctx.add_include_maybe(fqn)
        c_name = fqn.c_name
        c_args = [self.fmt_expr(arg) for arg in call.args]
        return C.Call(c_name, c_args)

    def fmt_struct_make(self, fqn: FQN, call: ast.Call, irtag: IRTag) -> C.Expr:
        c_structtype = self.ctx.c_restype_by_fqn(fqn)
        c_args = [self.fmt_expr(arg) for arg in call.args]
        strargs = ", ".join(map(str, c_args))
        return C.Cast(c_structtype, C.Literal("{ %s }" % strargs))

    def fmt_struct_getfield(self, fqn: FQN, call: ast.Call, irtag: IRTag) -> C.Expr:
        assert len(call.args) == 1
        c_struct = self.fmt_expr(call.args[0])
        name = irtag.data["name"]
        return C.Dot(c_struct, name)

    def fmt_ptr_getfield(self, fqn: FQN, call: ast.Call, irtag: IRTag) -> C.Expr:
        assert isinstance(call.args[1], ast.StrConst)
        c_ptr = self.fmt_expr(call.args[0])
        attr = call.args[1].value
        offset = call.args[2]  # ignored
        c_field = C.PtrField(c_ptr, attr)
        if irtag.data["by"] == "byref":
            c_restype = self.ctx.c_restype_by_fqn(fqn)
            return C.PtrFieldByRef(c_restype, c_field)
        else:
            return c_field

    def fmt_ptr_setfield(self, fqn: FQN, call: ast.Call) -> C.Expr:
        assert isinstance(call.args[1], ast.StrConst)
        c_ptr = self.fmt_expr(call.args[0])
        attr = call.args[1].value
        offset = call.args[2]  # ignored
        c_lval = C.PtrField(c_ptr, attr)
        c_rval = self.fmt_expr(call.args[3])
        return C.BinOp("=", c_lval, c_rval)
