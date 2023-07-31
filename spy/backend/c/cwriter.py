from typing import Optional, Any
import itertools
import py.path
from spy.vm.object import W_Type, W_Object, W_i32
from spy.vm.str import W_str
from spy.vm.module import W_Module
from spy.vm.function import W_Function, W_FunctionType
from spy.vm.codeobject import OpCode
from spy.vm.vm import SPyVM
from spy.vm import helpers
from spy.textbuilder import TextBuilder
from spy.backend.c.context import Context, C_Type, C_Function
from spy.backend.c import expr as c_expr
from spy.util import shortrepr

class CModuleWriter:
    w_mod: W_Module
    out: TextBuilder          # main builder
    out_globals: TextBuilder  # nested builder for global declarations
    global_vars: set[str]

    def __init__(self, vm: SPyVM, w_mod: W_Module) -> None:
        self.ctx = Context(vm)
        self.w_mod = w_mod
        self.out = TextBuilder(use_colors=False)
        self.out_globals = None  # type: ignore
        self.global_vars = set()

    def write_c_source(self, outfile: py.path.local) -> None:
        c_src = self.emit_module()
        outfile.write(c_src)

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
        self.out.wl('#include <spy.h>')
        self.out.wl()
        self.out.wl('// global declarations and definitions')
        self.out_globals = self.out.make_nested_builder()
        self.out.wl()
        self.out.wl('// content of the module')
        # XXX we should pre-declare variables and functions
        for name, w_obj in self.w_mod.content.values_w.items():
            assert w_obj is not None, 'uninitialized global?'
            # XXX we should mangle the name somehow
            if isinstance(w_obj, W_Function):
                self.emit_function(name, w_obj)
            else:
                self.emit_variable(name, w_obj)
        return self.out.build()

    def emit_function(self, name: str, w_func: W_Function) -> None:
        fw = CFuncWriter(self.ctx, self, name, w_func)
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
    cmod: CModuleWriter
    out: TextBuilder
    name: str
    w_func: W_Function
    tmp_vars: dict[str, C_Type]
    stack: list[c_expr.Expr]

    def __init__(self, ctx: Context,
                 cmod: CModuleWriter,
                 name: str, w_func: W_Function):
        self.ctx = ctx
        self.cmod = cmod
        self.out = cmod.out
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

    # === methods to control the iteration over the opcodes ===

    def advance(self) -> Optional[OpCode]:
        """
        Move to the next op.
        """
        i = self.next_op_index
        if i >= len(self.w_func.w_code.body):
            return None
        op = self.w_func.w_code.body[i]
        self.next_op_index += 1
        return op

    def advance_and_emit(self) -> OpCode:
        """
        Move to the next op and emit it
        """
        op = self.advance()
        assert op is not None
        self.emit_op(op)
        return op

    def consume(self, expected_name: str, *args: Any) -> OpCode:
        """
        Consume the next op without emitting it.
        """
        op = self.advance()
        assert op, 'Unexpected EOF of body'
        assert op.match(expected_name, *args)
        return op

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
        elif w_type is b.w_str:
            assert isinstance(w_obj, W_str)
            self._emit_op_load_str(w_obj)
        else:
            raise NotImplementedError('WIP')

    def _emit_op_load_str(self, w_obj: W_str) -> None:
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
        utf8 = w_obj.get_utf8()
        v = self.cmod.new_global_var('str')  # SPY_g_str0
        n = len(utf8)
        lit = c_expr.Literal.from_bytes(utf8)
        init = '{%d, %s}' % (n, lit.str())
        self.cmod.out_globals.wl(f'static spy_Str {v} = {init};')
        #
        # shortstr is what we show in the comment, with a length limit
        comment = shortrepr(utf8.decode('utf-8'), 15)
        v = f'{v} /* {comment} */'
        res = c_expr.UnaryOp('&', c_expr.Literal(v))
        self.push(res)

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

    def _pop_args(self, argcount: int) -> str:
        args = []
        for i in range(argcount):
            args.append(self.pop().str())
        args.reverse()
        arglist = ', '.join(args)
        return arglist

    def emit_op_call_global(self, funcname: str, argcount: int) -> None:
        arglist = self._pop_args(argcount)
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

    def emit_op_call_helper(self, funcname: str, argcount: int) -> None:
        # determine the c_restype by looking at the signature of the helper
        helper_func = helpers.get(funcname)
        pycls = helper_func.__annotations__['return']
        assert issubclass(pycls, W_Object)
        w_restype = self.ctx.vm.wrap(pycls)
        assert isinstance(w_restype, W_Type)
        c_restype = self.ctx.w2c(w_restype)
        #
        arglist = self._pop_args(argcount)
        tmp = self.new_var(c_restype)
        self.out.wl(f'{c_restype} {tmp} = spy_{funcname}({arglist});')
        self.push(c_expr.Literal(tmp))

    def emit_op_pop_and_discard(self) -> None:
        self.pop()

    ## ====== mark operations =====
    ## These are special ops We use op_mark_* to recognize the various higher
    ## level patterns which are emitted by the codegen, such as if/then,
    ## if/then/else, while, and we use these to emit "proper" C code.
    ##
    ## Note that this is not strictly necessary: we could easily implement
    ## ifs and loops using just gotos, but by doing this we generate C code
    ## which is WAY easier to read by humans, which simplifies a lot the
    ## debugging.

    def emit_op_mark_if_then(self, IF: int, END: int) -> None:
        """
        CodeGen._do_exec_If_then emits the following:

             mark_if_then IF, END
             <eval cond>
        IF:  br_if_not END
             <then body>
        END: <rest of the program>
        """
        while self.next_op_index < IF:
            self.advance_and_emit()
        #
        self.consume('br_if_not', END)
        cond = self.pop()
        self.out.wl(f'if ({cond.str()}) ' + '{')
        #
        with self.out.indent():
            while self.next_op_index < END:
                self.advance_and_emit()
        self.out.wl('}')

    def emit_op_mark_if_then_else(self, IF: int, ELSE: int, END: int) -> None:
        """
        CodeGen._do_exec_If_then_else emits the following:

              mark_if_then_else IF, ELSE, END
              <eval cond>
        IF:   br_if_not ELSE
              <then body>
              br END
        ELSE: <else body>
        END:  <rest of the program>
        """
        while self.next_op_index < IF:
            self.advance_and_emit()
        cond = self.pop()
        self.out.wl(f'if ({cond.str()}) ' + '{')
        self.consume('br_if_not', ELSE)
        #
        # emit the 'then'
        with self.out.indent():
            # note: we go up to ELSE-1 because we do NOT want to emit the 'br'
            while self.next_op_index < ELSE - 1:
                self.advance_and_emit()
        self.consume('br', END)
        # emit the 'else'
        self.out.wl('} else {')
        with self.out.indent():
            while self.next_op_index < END:
                self.advance_and_emit()
        self.out.wl('}')

    def emit_op_mark_while(self, IF: int, LOOP: int) -> None:
        """
        CodeGen.do_exec_While emits the following:

               mark_while IF LOOP
        START: <eval cond>
        IF:    br_if_not END
               <body>
        LOOP:  br START
        END:   <rest of the program>
        """
        self.out.wl('while(1) {')
        with self.out.indent():
            # <eval cond>
            while self.next_op_index < IF:
                self.advance_and_emit()
            #
            self.consume('br_if_not', ...)
            cond = self.pop()
            not_cond = c_expr.UnaryOp('!', cond)
            self.out.wl(f'if ({not_cond.str()})')
            self.out.wl('    break;')
            #
            # <body>
            while self.next_op_index < LOOP:
                self.advance_and_emit()
            self.consume('br', ...)
        self.out.wl('}')
