from typing import Optional, Any
from types import NoneType
import itertools
import py.path
from spy import ast
from spy.fqn import FQN
from spy.location import Loc
from spy.vm.object import W_Type, W_Object
from spy.vm.module import W_Module
from spy.vm.function import W_ASTFunc, W_BuiltinFunc, W_FuncType, W_Func
from spy.vm.vm import SPyVM
from spy.vm.b import B
from spy.vm.modules.types import TYPES
from spy.vm.modules.unsafe.struct import W_StructType
from spy.textbuilder import TextBuilder
from spy.backend.c.context import Context, C_Type, C_Function
from spy.backend.c import c_ast as C
from spy.util import shortrepr, magic_dispatch

class CModuleWriter:
    ctx: Context
    w_mod: W_Module
    spyfile: py.path.local
    cfile: py.path.local
    target: str
    out: TextBuilder          # main builder
    out_warnings: TextBuilder # nested builder
    out_types: TextBuilder    # nested builder
    out_globals: TextBuilder  # nested builder for global declarations
    global_vars: set[str]

    def __init__(self, vm: SPyVM, w_mod: W_Module,
                 spyfile: py.path.local,
                 cfile: py.path.local,
                 target: str) -> None:
        self.ctx = Context(vm)
        self.w_mod = w_mod
        self.spyfile = spyfile
        self.cfile = cfile
        self.target = target
        self.out = TextBuilder(use_colors=False)
        self.out_warnings = None  # type: ignore
        self.out_types = None     # type: ignore
        self.out_globals = None   # type: ignore
        self.global_vars = set()

    def write_c_source(self) -> None:
        c_src = self.emit_module()
        self.cfile.write(c_src)

    def new_global_var(self, prefix: str) -> str:
        """
        Create an unique name for a global var whose name starts with 'prefix'
        """
        prefix = f'SPY_g_{prefix}'
        for i in itertools.count():
            varname = f'{prefix}{i}'
            if varname not in self.global_vars:
                break
        self.global_vars.add(varname)
        return varname

    def emit_module(self) -> str:
        self.out.wb(f"""
        #include <spy.h>

        #ifdef SPY_DEBUG_C
        #    define SPY_LINE(SPY, C) C "{self.cfile}"
        #else
        #    define SPY_LINE(SPY, C) SPY "{self.spyfile}"
        #endif

        // global declarations and definitions
        """)
        self.out_warnings = self.out.make_nested_builder()
        self.out_types = self.out.make_nested_builder()
        self.out_globals = self.out.make_nested_builder()
        self.out.wl()

        # this is a bit of a hack, but too bad
        self.ctx.out_types = self.out_types

        self.out.wb("""
        // content of the module
        """)
        #
        for fqn, w_obj in self.w_mod.items_w():
            assert w_obj is not None, 'uninitialized global?'
            # XXX we should mangle the name somehow
            if isinstance(w_obj, W_ASTFunc):
                if w_obj.color == 'red':
                    self.declare_function(fqn, w_obj)
                    self.emit_function(fqn, w_obj)
            elif isinstance(w_obj, W_BuiltinFunc):
                # this is a hack. We have a variable holding a builtin
                # function: we don't support function pointers yet, so this
                # MUST be a blue variable, which we don't want to declare, so
                # we just skip it.
                #
                # Ideally, we should have a more direct way of knowing which
                # of the module content are red and blue.
                pass
            else:
                self.declare_variable(fqn, w_obj)

        # XXX: this is probably broken in case we are compiling together
        # multiple modules with a 'main' function, but it's ok for now
        fqn_main = FQN.make(modname=self.w_mod.name, attr='main', suffix="")
        if fqn_main in self.ctx.vm.globals_w:
            self.out.wb(f"""
                int main(void) {{
                    {fqn_main.c_name}();
                    return 0;
                }}
            """)
        return self.out.build()

    def emit_jsffi_error(self) -> None:
        err = '#error "jsffi is available only for emscripten targets"'
        if err not in self.out_warnings.lines:
            self.out_warnings.wl(err)

    def declare_function(self, fqn: FQN, w_func: W_ASTFunc) -> None:
        c_func = self.ctx.c_function(fqn.c_name, w_func.w_functype)
        self.out_globals.wl(c_func.decl() + ';')

    def emit_function(self, fqn: FQN, w_func: W_ASTFunc) -> None:
        fw = CFuncWriter(self.ctx, self, fqn, w_func)
        fw.emit()

    def declare_variable(self, fqn: FQN, w_obj: W_Object) -> None:
        w_type = self.ctx.vm.dynamic_type(w_obj)
        if w_type is B.w_i32:
            intval = self.ctx.vm.unwrap(w_obj)
            c_type = self.ctx.w2c(w_type)
            self.out_globals.wl(f'{c_type} {fqn.c_name} = {intval};')
        elif w_type is B.w_type and isinstance(w_obj, W_StructType):
            # this forces ctx to emit the struct definition
            self.ctx.w2c(w_obj)
        elif w_type is TYPES.w_TypeDef:
            # XXX: for now, we just ignore global TypeDefs, since they are not
            # needed. But in general, we need a way to emit prebuilt
            # constants.
            pass
        else:
            raise NotImplementedError('WIP')


class CFuncWriter:
    ctx: Context
    cmod: CModuleWriter
    out: TextBuilder
    fqn: FQN
    w_func: W_ASTFunc
    last_emitted_linenos: tuple[int, int]

    def __init__(self,
                 ctx: Context,
                 cmod: CModuleWriter,
                 fqn: FQN,
                 w_func: W_ASTFunc) -> None:
        self.ctx = ctx
        self.cmod = cmod
        self.out = cmod.out
        self.fqn = fqn
        self.w_func = w_func
        self.last_emitted_linenos = (-1, -1) # see emit_lineno_maybe

    def ppc(self) -> None:
        """
        Pretty print the C code generated so far
        """
        print(self.out.build())

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
        c_func = self.ctx.c_function(self.fqn.c_name,
                                     self.w_func.w_functype)
        self.out.wl(c_func.decl() + ' {')
        with self.out.indent():
            self.emit_local_vars()
            for stmt in self.w_func.funcdef.body:
                self.emit_stmt(stmt)

            if self.w_func.w_functype.w_restype is not B.w_void:
                # this is a non-void function: if we arrive here, it means we
                # reached the end of the function without a return. Ideally,
                # we would like to also report an error message, but for now
                # we just abort.
                msg = 'reached the end of the function without a `return`'
                self.out.wl(f'abort(); /* {msg} */')
        self.out.wl('}')

    def emit_local_vars(self) -> None:
        """
        Declare all local variables.

        We need to declare all of them in advance because C scoping rules are
        different than SPy scoping rules, so we emit the C declaration when we
        see e.g. a VarDef.
        """
        assert self.w_func.locals_types_w is not None
        param_names = [p.name for p in self.w_func.w_functype.params]
        for varname, w_type in self.w_func.locals_types_w.items():
            c_type = self.ctx.w2c(w_type)
            if varname != '@return' and varname not in param_names:
                self.out.wl(f'{c_type} {varname};')

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
        cur_c = self.out.lineno
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
        cline = self.out.lineno
        self.out.wl(f'#line SPY_LINE({spyline}, {cline})')
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
            self.out.wl('return;')
        else:
            self.out.wl(f'return {v};')

    def emit_stmt_VarDef(self, vardef: ast.VarDef) -> None:
        # all local vars have already been declared, nothing to do
        pass

    def emit_stmt_Assign(self, assign: ast.Assign) -> None:
        v = self.fmt_expr(assign.value)
        sym = self.w_func.funcdef.symtable.lookup(assign.target)
        if sym.is_local:
            target = assign.target
        else:
            target = sym.fqn.c_name
        self.out.wl(f'{target} = {v};')

    def emit_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> None:
        v = self.fmt_expr(stmt.value);
        self.out.wl(f'{v};')

    def emit_stmt_If(self, if_node: ast.If) -> None:
        test = self.fmt_expr(if_node.test)
        self.out.wl(f'if ({test})' + '{')
        with self.out.indent():
            for stmt in if_node.then_body:
                self.emit_stmt(stmt)
        #
        if if_node.else_body:
            self.out.wl('} else {')
            for stmt in if_node.else_body:
                self.emit_stmt(stmt)
        #
        self.out.wl('}')

    def emit_stmt_While(self, while_node: ast.While) -> None:
        test = self.fmt_expr(while_node.test)
        self.out.wl(f'while ({test}) ' + '{')
        with self.out.indent():
            for stmt in while_node.body:
                self.emit_stmt(stmt)
        self.out.wl('}')

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
        elif T is str:
            assert isinstance(const.value, str)
            return self._fmt_str_literal(const.value)
        else:
            raise NotImplementedError('WIP')

    def _fmt_str_literal(self, s: str) -> C.Expr:
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
        utf8 = s.encode('utf-8')
        v = self.cmod.new_global_var('str')  # SPY_g_str0
        n = len(utf8)
        lit = C.Literal.from_bytes(utf8)
        init = '{%d, %s}' % (n, lit)
        self.cmod.out_globals.wl(f'static spy_Str {v} = {init};')
        #
        # shortstr is what we show in the comment, with a length limit
        comment = shortrepr(utf8.decode('utf-8'), 15)
        v = f'{v} /* {comment} */'
        return C.UnaryOp('&', C.Literal(v))

    def fmt_expr_FQNConst(self, const: ast.FQNConst) -> C.Expr:
        w_obj = self.ctx.vm.lookup_global(const.fqn)
        assert isinstance(w_obj, W_Func)
        return C.Literal(const.fqn.c_name)

    def fmt_expr_Name(self, name: ast.Name) -> C.Expr:
        sym = self.w_func.funcdef.symtable.lookup(name.id)
        if sym.is_local:
            return C.Literal(name.id)
        else:
            return C.Literal(sym.fqn.c_name)

    def fmt_expr_BinOp(self, binop: ast.BinOp) -> C.Expr:
        raise NotImplementedError(
            'ast.BinOp not supported. It should have been redshifted away')

    fmt_expr_Add = fmt_expr_BinOp
    fmt_expr_Sub = fmt_expr_BinOp
    fmt_expr_Mul = fmt_expr_BinOp
    fmt_expr_Div = fmt_expr_BinOp
    fmt_expr_Eq = fmt_expr_BinOp
    fmt_expr_NotEq = fmt_expr_BinOp
    fmt_expr_Lt = fmt_expr_BinOp
    fmt_expr_LtE = fmt_expr_BinOp
    fmt_expr_Gt = fmt_expr_BinOp
    fmt_expr_GtE = fmt_expr_BinOp


    FQN2BinOp = {
        FQN.parse('operator::i32_add'): '+',
        FQN.parse('operator::i32_sub'): '-',
        FQN.parse('operator::i32_mul'): '*',
        FQN.parse('operator::i32_div'): '/', # XXX: floor or int division?
        FQN.parse('operator::i32_eq') : '==',
        FQN.parse('operator::i32_ne') : '!=',
        FQN.parse('operator::i32_lt') : '<',
        FQN.parse('operator::i32_le') : '<=',
        FQN.parse('operator::i32_gt') : '>',
        FQN.parse('operator::i32_ge') : '>=',
        #
        FQN.parse('operator::f64_add'): '+',
        FQN.parse('operator::f64_sub'): '-',
        FQN.parse('operator::f64_mul'): '*',
        FQN.parse('operator::f64_div'): '/',
        FQN.parse('operator::f64_eq') : '==',
        FQN.parse('operator::f64_ne') : '!=',
        FQN.parse('operator::f64_lt') : '<',
        FQN.parse('operator::f64_le') : '<=',
        FQN.parse('operator::f64_gt') : '>',
        FQN.parse('operator::f64_ge') : '>=',
    }

    def fmt_expr_Call(self, call: ast.Call) -> C.Expr:
        assert isinstance(call.func, ast.FQNConst), \
            'indirect calls are not supported yet'

        # some calls are special-cased and transformed into a C binop
        op = self.FQN2BinOp.get(call.func.fqn)
        if op is not None:
            assert len(call.args) == 2
            l, r = [self.fmt_expr(arg) for arg in call.args]
            return C.BinOp(op, l, r)

        if call.func.fqn.modname == "jsffi" and self.cmod.target != 'emscripten':
            self.cmod.emit_jsffi_error()

        # FIXME: many of the following special-cases are needed because the
        # signature of the opimpl doesn't match the needed signature of the
        # corresponding C function. E.g.:
        #
        #   - int2str: the first param is the 'str' type but we remove it
        #
        #   - jsffi::getattr: the current sig for GETATTR does not pass the
        #     attribute name, but we want it as a C literal. The hack is to
        #     pass it as part of the builtin name (e.g.,
        #     jsffi::getattr_document) and parse it. Same for jsffi::setattr
        #
        #   - jsffi::call_method_1: the method name is a W_Str but we want a C
        #     literal, so we hack it
        #
        # I think we need a more general way so that OPERATORs can have more
        # control on which arguments are passed to opimpls.

        if str(call.func.fqn).startswith("jsffi::getattr_"):
            assert isinstance(call.args[1], ast.Constant)
            c_name = "jsffi_getattr"
            attr = call.args[1].value
            c_obj = self.fmt_expr(call.args[0])
            c_attr = C.Literal(f'"{attr}"')
            return C.Call(c_name, [c_obj, c_attr])

        # horrible hack (see also jsffi.W_JsRef.op_SETATTR)
        if str(call.func.fqn).startswith("jsffi::setattr_"):
            assert isinstance(call.args[1], ast.Constant)
            c_name = "jsffi_setattr"
            c_obj = self.fmt_expr(call.args[0])
            attr = call.args[1].value
            c_attr = C.Literal(f'"{attr}"')
            c_value = self.fmt_expr(call.args[2])
            return C.Call(c_name, [c_obj, c_attr, c_value])

        if call.func.fqn == FQN.parse("jsffi::call_method_1"):
            assert isinstance(call.args[1], ast.Constant)
            c_name = "jsffi_call_method_1"
            c_obj = self.fmt_expr(call.args[0])
            attr = call.args[1].value
            c_attr = C.Literal(f'"{attr}"')
            c_arg = self.fmt_expr(call.args[2])
            return C.Call(c_name, [c_obj, c_attr, c_arg])

        if str(call.func.fqn).startswith("unsafe::getfield_prim"):
            c_ptr = self.fmt_expr(call.args[0])
            attr = call.args[1].value
            offset = call.args[2]  # ignored
            return C.SPyField(c_ptr, attr)

        if str(call.func.fqn).startswith("unsafe::getfield_ref"):
            c_ptr = self.fmt_expr(call.args[0])
            attr = call.args[1].value
            offset = call.args[2]  # ignored
            c_field = C.SPyField(c_ptr, attr)
            c_restype = self.ctx.c_restype_by_fqn(call.func.fqn)
            return C.SPyFieldRef(c_restype, c_field)

        if str(call.func.fqn).startswith("unsafe::setfield_"):
            c_ptr = self.fmt_expr(call.args[0])
            attr = call.args[1].value
            offset = call.args[2]  # ignored
            c_lval = C.SPyField(c_ptr, attr)
            c_rval = self.fmt_expr(call.args[3])
            return C.BinOp('=', c_lval, c_rval)

        # the default case is to call a function with the corresponding name
        c_name = call.func.fqn.c_name
        c_args = [self.fmt_expr(arg) for arg in call.args]
        return C.Call(c_name, c_args)
