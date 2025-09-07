from typing import TYPE_CHECKING
from types import NoneType
from spy import ast
from spy.fqn import FQN
from spy.location import Loc
from spy.vm.function import W_ASTFunc, W_Func
from spy.vm.b import B
from spy.vm.modules.unsafe.ptr import W_Ptr
from spy.textbuilder import TextBuilder
from spy.backend.c.context import Context
from spy.backend.c import c_ast as C
from spy.util import shortrepr, magic_dispatch

if TYPE_CHECKING:
    from spy.backend.c.cmodwriter import CModuleWriter


class CFuncWriter:
    ctx: Context
    cmodw: 'CModuleWriter'
    tbc: TextBuilder
    fqn: FQN
    w_func: W_ASTFunc
    last_emitted_linenos: tuple[int, int]

    def __init__(self,
                 ctx: Context,
                 cmodw: 'CModuleWriter',
                 fqn: FQN,
                 w_func: W_ASTFunc) -> None:
        self.ctx = ctx
        self.cmodw = cmodw
        self.tbc = cmodw.tbc
        self.fqn = fqn
        self.w_func = w_func
        self.last_emitted_linenos = (-1, -1) # see emit_lineno_maybe

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
        self.tbc.wl(c_func.decl() + ' {')
        with self.tbc.indent():
            self.emit_local_vars()
            for stmt in self.w_func.funcdef.body:
                self.emit_stmt(stmt)

            if self.w_func.w_functype.w_restype is not B.w_NoneType:
                # this is a non-void function: if we arrive here, it means we
                # reached the end of the function without a return. Ideally,
                # we would like to also report an error message, but for now
                # we just abort.
                msg = 'reached the end of the function without a `return`'
                self.tbc.wl(f'abort(); /* {msg} */')
        self.tbc.wl('}')

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
            if (varname not in ('@return', '@if', '@while') and
                varname not in param_names):
                self.tbc.wl(f'{c_type} {varname};')

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
        self.tbc.wl(f'#line SPY_LINE({spyline}, {cline})')
        self.last_emitted_linenos = (spyline, cline)

    def emit_stmt(self, stmt: ast.Stmt) -> None:
        self.emit_lineno_maybe(stmt.loc)
        magic_dispatch(self, 'emit_stmt', stmt)

    def fmt_expr(self, expr: ast.Expr) -> C.Expr:
        # XXX: here we should probably handle typeconv, if present.
        # However, we cannot yet write a test for it because:
        #   - we cannot test DynamicCast because we don't support object
        #   - we cannot test NumericConv because the expressions are
        #     automatically converted by the C compiler anyway
        return magic_dispatch(self, 'fmt_expr', expr)

    # ===== statements =====

    def emit_stmt_Pass(self, stmt: ast.Pass) -> None:
        pass

    def emit_stmt_Return(self, ret: ast.Return) -> None:
        v = self.fmt_expr(ret.value)
        if v is C.Void():
            self.tbc.wl('return;')
        else:
            self.tbc.wl(f'return {v};')

    def emit_stmt_VarDef(self, vardef: ast.VarDef) -> None:
        # all local vars have already been declared, nothing to do
        pass

    def emit_stmt_Assign(self, assign: ast.Assign) -> None:
        assert False, 'ast.Assign nodes should not survive redshifting'

    def emit_stmt_AssignLocal(self, assign: ast.AssignLocal) -> None:
        target = assign.target.value
        v = self.fmt_expr(assign.value)
        self.tbc.wl(f'{target} = {v};')

    def emit_stmt_AssignCell(self, assign: ast.AssignCell) -> None:
        v = self.fmt_expr(assign.value)
        target = assign.target_fqn.c_name
        self.tbc.wl(f'{target} = {v};')

    def emit_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> None:
        v = self.fmt_expr(stmt.value);
        self.tbc.wl(f'{v};')

    def emit_stmt_If(self, if_node: ast.If) -> None:
        test = self.fmt_expr(if_node.test)
        self.tbc.wl(f'if ({test})' + '{')
        with self.tbc.indent():
            for stmt in if_node.then_body:
                self.emit_stmt(stmt)
        #
        if if_node.else_body:
            self.tbc.wl('} else {')
            with self.tbc.indent():
                for stmt in if_node.else_body:
                    self.emit_stmt(stmt)
        #
        self.tbc.wl('}')

    def emit_stmt_While(self, while_node: ast.While) -> None:
        test = self.fmt_expr(while_node.test)
        self.tbc.wl(f'while ({test}) ' + '{')
        with self.tbc.indent():
            for stmt in while_node.body:
                self.emit_stmt(stmt)
        self.tbc.wl('}')

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
            raise NotImplementedError('WIP')

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
        utf8 = s.encode('utf-8')
        v = self.cmodw.new_global_var('str')  # SPY_g_str0
        n = len(utf8)
        lit = C.Literal.from_bytes(utf8)
        init = '{%d, %s}' % (n, lit)
        self.cmodw.tbc_globals.wl(f'static spy_Str {v} = {init};')
        #
        # shortstr is what we show in the comment, with a length limit
        comment = shortrepr(utf8.decode('utf-8'), 15)
        v = f'{v} /* {comment} */'
        return C.UnaryOp('&', C.Literal(v))

    def fmt_expr_FQNConst(self, const: ast.FQNConst) -> C.Expr:
        w_obj = self.ctx.vm.lookup_global(const.fqn)
        if isinstance(w_obj, W_Ptr):
            # for each PtrType, we emit the corresponding NULL define with the
            # appropriate fqn name, see Context.new_ptr_type
            assert w_obj.addr == 0, 'only NULL ptrs can be constants'
            return C.Literal(const.fqn.c_name)
        elif isinstance(w_obj, W_Func):
            return C.Literal(const.fqn.c_name)
        else:
            assert False

    def fmt_expr_Name(self, name: ast.Name) -> C.Expr:
        assert False, 'ast.Name nodes should not survive redshifting'

    def fmt_expr_NameLocal(self, name: ast.NameLocal) -> C.Expr:
        return C.Literal(name.sym.name)

    def fmt_expr_NameOuterCell(self, name: ast.NameOuterCell) -> C.Expr:
        return C.Literal(name.fqn.c_name)

    def fmt_expr_NameOuterDirect(self, name: ast.NameOuterDirect) -> C.Expr:
        # at the moment of writing, closed-over variables are always blue, so
        # they should not survive redshifting
        assert False, 'unexepcted NameOuterDirect'

    def fmt_expr_BinOp(self, binop: ast.BinOp) -> C.Expr:
        raise NotImplementedError(
            'ast.BinOp not supported. It should have been redshifted away')

    FQN2BinOp = {
        FQN('operator::i8_add'): '+',
        FQN('operator::i8_sub'): '-',
        FQN('operator::i8_mul'): '*',
        FQN('operator::i8_floordiv'): '/',
        FQN('operator::i8_mod'): '%',
        FQN('operator::i8_lshift'): '<<',
        FQN('operator::i8_rshift'): '>>',
        FQN('operator::i8_and'): '&',
        FQN('operator::i8_or'): '|',
        FQN('operator::i8_xor'): '^',
        FQN('operator::i8_eq') : '==',
        FQN('operator::i8_ne') : '!=',
        FQN('operator::i8_lt') : '<',
        FQN('operator::i8_le') : '<=',
        FQN('operator::i8_gt') : '>',
        FQN('operator::i8_ge') : '>=',
        #
        FQN('operator::u8_add'): '+',
        FQN('operator::u8_sub'): '-',
        FQN('operator::u8_mul'): '*',
        FQN('operator::u8_floordiv'): '/',
        FQN('operator::u8_mod'): '%',
        FQN('operator::u8_lshift'): '<<',
        FQN('operator::u8_rshift'): '>>',
        FQN('operator::u8_and'): '&',
        FQN('operator::u8_or'): '|',
        FQN('operator::u8_xor'): '^',
        FQN('operator::u8_eq') : '==',
        FQN('operator::u8_ne') : '!=',
        FQN('operator::u8_lt') : '<',
        FQN('operator::u8_le') : '<=',
        FQN('operator::u8_gt') : '>',
        FQN('operator::u8_ge') : '>=',
        #
        FQN('operator::i32_add'): '+',
        FQN('operator::i32_sub'): '-',
        FQN('operator::i32_mul'): '*',
        FQN('operator::i32_floordiv'): '/',
        FQN('operator::i32_mod'): '%',
        FQN('operator::i32_lshift'): '<<',
        FQN('operator::i32_rshift'): '>>',
        FQN('operator::i32_and'): '&',
        FQN('operator::i32_or'): '|',
        FQN('operator::i32_xor'): '^',
        FQN('operator::i32_eq') : '==',
        FQN('operator::i32_ne') : '!=',
        FQN('operator::i32_lt') : '<',
        FQN('operator::i32_le') : '<=',
        FQN('operator::i32_gt') : '>',
        FQN('operator::i32_ge') : '>=',
        #
        FQN('operator::f64_add'): '+',
        FQN('operator::f64_sub'): '-',
        FQN('operator::f64_mul'): '*',
        FQN('operator::f64_div'): '/',
        FQN('operator::f64_eq') : '==',
        FQN('operator::f64_ne') : '!=',
        FQN('operator::f64_lt') : '<',
        FQN('operator::f64_le') : '<=',
        FQN('operator::f64_gt') : '>',
        FQN('operator::f64_ge') : '>=',

        # the following are NOT special cased, and are implemented in
        # operator.h. They are listed here to make emphasize that they are not
        # omitted from above by mistake:
        # FQN('operator::i8_div')
        # FQN('operator::u8_div')
        # FQN('operator::i32_div')
        # FQN('operator::f64_floordiv')
    }

    FQN2UnaryOp = {
        FQN('operator::i8_neg'): '-',
        FQN('operator::i32_neg'): '-',
        FQN('operator::f64_neg'): '-',
    }

    def fmt_expr_Call(self, call: ast.Call) -> C.Expr:
        assert isinstance(call.func, ast.FQNConst), \
            'indirect calls are not supported yet'

        # some calls are special-cased and transformed into a C binop
        if op := self.FQN2BinOp.get(call.func.fqn):
            assert len(call.args) == 2
            l, r = [self.fmt_expr(arg) for arg in call.args]
            return C.BinOp(op, l, r)

        if op := self.FQN2UnaryOp.get(call.func.fqn):
            assert len(call.args) == 1
            v = self.fmt_expr(call.args[0])
            return C.UnaryOp(op, v)

        if call.func.fqn.modname == "jsffi":
            self.cmodw.emit_jsffi_error_maybe()

        fqn = call.func.fqn
        if str(fqn).startswith("unsafe::getfield_by"):
            return self.fmt_getfield(fqn, call)
        elif str(fqn).startswith("unsafe::setfield["):
            return self.fmt_setfield(fqn, call)
        elif (fqn.match("unsafe::ptr[*]::getitem_by*") or
              fqn.match("unsafe::ptr[*]::store")):
            # see unsafe/ptr.py::w_GETITEM and w_SETITEM there, we insert an
            # extra "w_loc" argument, which is not needed by the C backend
            # because we rely on C's own mechanism to get line numbers.
            # Moreover, we don't have a way to render "W_Loc" consts to C.
            #
            # So, we just remove the last arguments. Note that this much match
            # with the signature of the load/store functions generated by
            # unsafe.h:SPY_PTR_FUNCTIONS.
            assert isinstance(call.args[-1], ast.LocConst)
            call.args.pop() # remove it

        # the default case is to call a function with the corresponding name
        self.ctx.add_include_maybe(fqn)
        c_name = fqn.c_name
        c_args = [self.fmt_expr(arg) for arg in call.args]
        return C.Call(c_name, c_args)

    def fmt_getfield(self, fqn: FQN, call: ast.Call) -> C.Expr:
        assert isinstance(call.args[1], ast.StrConst)
        is_byref = str(fqn).startswith("unsafe::getfield_byref")
        c_ptr = self.fmt_expr(call.args[0])
        attr = call.args[1].value
        offset = call.args[2]  # ignored
        c_field = C.PtrField(c_ptr, attr)
        if is_byref:
            c_restype = self.ctx.c_restype_by_fqn(fqn)
            return C.PtrFieldByRef(c_restype, c_field)
        else:
            return c_field

    def fmt_setfield(self, fqn: FQN, call: ast.Call) -> C.Expr:
        assert isinstance(call.args[1], ast.StrConst)
        c_ptr = self.fmt_expr(call.args[0])
        attr = call.args[1].value
        offset = call.args[2]  # ignored
        c_lval = C.PtrField(c_ptr, attr)
        c_rval = self.fmt_expr(call.args[3])
        return C.BinOp('=', c_lval, c_rval)
