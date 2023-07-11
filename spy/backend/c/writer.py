from typing import Optional
from py.path import LocalPath
from spy.vm.object import W_Type, W_Object, W_i32
from spy.vm.module import W_Module
from spy.vm.function import W_Function, W_FunctionType
from spy.vm.codeobject import OpCode
from spy.vm.vm import SPyVM
from spy.textbuilder import TextBuilder
from spy.backend.c.context import Context, C_Type, C_Function
from spy.backend.c import expr as c_expr

class CModuleWriter:
    w_mod: W_Module
    out: TextBuilder

    def __init__(self, vm: SPyVM, w_mod: W_Module) -> None:
        self.ctx = Context(vm)
        self.w_mod = w_mod
        self.out = TextBuilder(use_colors=False)

    def write_c_source(self, outfile: LocalPath) -> None:
        c_src = self.emit_module()
        outfile.write(c_src)

    def emit_module(self) -> str:
        self.out.wl('#include <stdint.h>')
        self.out.wl('#include <stdbool.h>')
        self.out.wl()
        # XXX we should pre-declare variables and functions
        for name, w_obj in self.w_mod.content.values_w.items():
            # XXX we should mangle the name somehow
            if isinstance(w_obj, W_Function):
                self.emit_function(name, w_obj)
            else:
                self.emit_variable(name, w_obj)
        return self.out.build()

    def emit_function(self, name: str, w_func: W_Function) -> None:
        fw = CFuncWriter(self.ctx, self.out, name, w_func)
        fw.emit()

    def emit_variable(self, name: str, w_obj: W_Object) -> None:
        b = self.ctx.vm.builtins
        w_type = self.ctx.vm.dynamic_type(w_obj)
        c_type = self.ctx.w2c(w_type)
        if w_type is b.w_i32:
            intval = self.ctx.vm.unwrap(w_obj)
            self.out.wl(f'{c_type} {name} = {intval};')
        else:
            raise NotImplementedError('WIP')


class CFuncWriter:
    ctx: Context
    name: str
    w_func: W_Function
    tmp_vars: dict[str, C_Type]
    stack: list[c_expr.Expr]

    def __init__(self, ctx: Context, out: TextBuilder, name: str,
                 w_func: W_Function):
        self.ctx = ctx
        self.out = out
        self.name = name
        self.w_func = w_func
        self.tmp_vars = {}
        self.stack = []
        self.next_op_index = 0

    def ppc(self) -> None:
        """
        Pretty print the C code generated so far
        """
        print(self.out.build())

    def ppir(self) -> None:
        """
        Pretty print the IR code
        """
        self.w_func.w_code.pp()

    def push(self, expr: c_expr.Expr) -> None:
        assert isinstance(expr, c_expr.Expr)
        self.stack.append(expr)

    def pop(self) -> c_expr.Expr:
        return self.stack.pop()

    def new_var(self, c_type: C_Type) -> str:
        n = len(self.tmp_vars)
        name = f'tmp{n}'
        self.tmp_vars[name] = c_type
        return name

    def emit(self) -> None:
        """
        Emit the code for the whole function
        """
        c_func = self.ctx.c_function(self.name, self.w_func.w_functype)
        self.out.wl(c_func.decl() + ' {')
        with self.out.indent():
            self.emit_local_vars()
            # emit the body
            self.next_op_index = 0
            while op := self.advance():
                self.emit_op(op)
            assert self.stack == []
        self.out.wl('}')

    def advance(self) -> Optional[OpCode]:
        i = self.next_op_index
        if i >= len(self.w_func.w_code.body):
            return None
        op = self.w_func.w_code.body[i]
        self.next_op_index += 1
        return op

    def advance_surely(self) -> OpCode:
        op = self.advance()
        assert op is not None
        return op

    def emit_local_vars(self) -> None:
        """
        Declare all local variables
        """
        param_names = [p.name for p in self.w_func.w_functype.params]
        for varname, w_type in self.w_func.w_code.locals_w_types.items():
            c_type = self.ctx.w2c(w_type)
            if varname not in param_names:
                self.out.wl(f'{c_type} {varname};')

    def emit_op(self, op: OpCode) -> None:
        meth_name = f'emit_op_{op.name}'
        meth = getattr(self, meth_name, None)
        if meth is None:
            raise NotImplementedError(meth_name)
        meth(*op.args)

    def emit_op_load_const(self, w_obj: W_Object) -> None:
        # XXX we need to share code with 'emit_variable'
        b = self.ctx.vm.builtins
        w_type = self.ctx.vm.dynamic_type(w_obj)
        c_type = self.ctx.w2c(w_type)
        if w_type is b.w_void:
            self.push(c_expr.Void())
        elif w_type is b.w_i32:
            intval = self.ctx.vm.unwrap(w_obj)
            self.push(c_expr.Literal(str(intval)))
        elif w_type is b.w_bool:
            boolval = self.ctx.vm.unwrap(w_obj)
            self.push(c_expr.Literal(str(boolval).lower()))
        else:
            raise NotImplementedError('WIP')

    def emit_op_return(self) -> None:
        expr = self.pop()
        if expr == c_expr.Void():
            # special case for void functions
            self.out.wl('return;')
        else:
            self.out.wl(f'return {expr.str()};')

    def emit_op_abort(self, msg: str) -> None:
        # XXX we ignore it for now
        pass

    def emit_op_load_local(self, varname: str) -> None:
        self.push(c_expr.Literal(varname))

    def emit_op_store_local(self, varname: str) -> None:
        expr = self.pop()
        self.out.wl(f'{varname} = {expr.str()};')

    emit_op_load_global = emit_op_load_local
    emit_op_store_global = emit_op_store_local

    def _emit_op_binop(self, op: str) -> None:
        right = self.pop()
        left = self.pop()
        expr = c_expr.BinOp(op, left, right)
        self.push(expr)

    def emit_op_i32_add(self) -> None:
        self._emit_op_binop('+')

    def emit_op_i32_mul(self) -> None:
        self._emit_op_binop('*')

    def emit_op_i32_eq(self) -> None:
        self._emit_op_binop('==')

    def emit_op_i32_neq(self) -> None:
        self._emit_op_binop('!=')

    def emit_op_i32_lt(self) -> None:
        self._emit_op_binop('<')

    def emit_op_i32_lte(self) -> None:
        self._emit_op_binop('<=')

    def emit_op_i32_gt(self) -> None:
        self._emit_op_binop('>')

    def emit_op_i32_gte(self) -> None:
        self._emit_op_binop('>=')

    def emit_op_call_global(self, funcname: str, argcount: int) -> None:
        args = []
        for i in range(argcount):
            args.append(self.pop().str())
        args.reverse()
        arglist = ', '.join(args)
        #
        w_functype = self.w_func.globals.types_w[funcname]
        assert isinstance(w_functype, W_FunctionType)
        w_restype = w_functype.w_restype
        c_restype = self.ctx.w2c(w_restype)
        #
        if w_restype is self.ctx.vm.builtins.w_void:
            self.out.wl(f'{funcname}({arglist});')
            self.push(c_expr.Void())
        else:
            tmp = self.new_var(c_restype)
            self.out.wl(f'{c_restype} {tmp} = {funcname}({arglist});')
            self.push(c_expr.Literal(tmp))

    def emit_op_pop_and_discard(self) -> None:
        self.pop()

    def emit_op_mark(self, marker: str) -> None:
        """
        This is a special op. We use op_mark to recognize the various higher level
        patterns which are emitted by the codegen, such as if/then,
        if/then/else, while, and we use these to emit "proper" C code.

        Note that this is not strictly necessary: we could easily implement
        ifs and loops using just gotos, but by doing this we generate C code
        which is WAY easier to read by humans, which simplifies a lot the
        debugging.
        """
        if marker == 'if_then':
            self.emit_if_then()
        elif marker == 'if_then_else':
            self.emit_if_then_else()
        else:
            raise NotImplementedError(f'Unknown marker: {marker}')

    def emit_if_then(self) -> None:
        """
        See CodeObject.validate_if_then for a visual description of the pattern
        which we expect
        """
        i = self.next_op_index - 1 # this is the index of the current op
        lbl_endif = self.w_func.w_code.validate_if_then(i)
        cond = self.pop()
        self.out.wl(f'if ({cond.str()}) ' + '{')
        with self.out.indent():
            assert self.advance_surely().name == 'br_if_not'  # consume the 'br_if_not'
            while self.next_op_index < lbl_endif:
                op = self.advance_surely()
                self.emit_op(op)
        self.out.wl('}')

    def emit_if_then_else(self) -> None:
        """
        See CodeObject.validate_if_then_else for a visual description of the
        pattern which we expect
        """
        i = self.next_op_index - 1 # this is the index of the current op
        lbl_else, lbl_endif = self.w_func.w_code.validate_if_then_else(i)
        cond = self.pop()
        self.out.wl(f'if ({cond.str()}) ' + '{')
        # emit the 'then'
        with self.out.indent():
            assert self.advance_surely().name == 'br_if_not'  # consume the 'br_if_not'
            # note: we go up to lbl_else-1 because we do NOT want to emit the 'br'
            while self.next_op_index < lbl_else - 1:
                op = self.advance_surely()
                self.emit_op(op)
        # emit the 'else'
        self.out.wl('} else {')
        with self.out.indent():
            assert self.advance_surely().name == 'br' # consume the 'br'
            while self.next_op_index < lbl_endif:
                op = self.advance_surely()
                self.emit_op(op)
        self.out.wl('}')
