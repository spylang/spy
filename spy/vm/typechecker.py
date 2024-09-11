from typing import TYPE_CHECKING, Optional, NoReturn, Any, Sequence, Literal
from types import NoneType
from spy import ast
from spy.fqn import QN, FQN
from spy.irgen.symtable import Symbol, Color
from spy.errors import (SPyTypeError, SPyNameError, maybe_plural)
from spy.location import Loc
from spy.vm.object import W_Object, W_Type
from spy.vm.opimpl import W_OpImpl, W_AbsVal
from spy.vm.list import W_List
from spy.vm.function import W_FuncType, W_ASTFunc, W_Func
from spy.vm.b import B
from spy.vm.modules.operator import OP
from spy.vm.modules.jsffi import JSFFI
from spy.vm.typeconverter import (TypeConverter, DynamicCast, NumericConv,
                                  JsRefConv)
from spy.vm.modules.types import W_TypeDef
from spy.util import magic_dispatch
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

W_List.make_prebuilt(W_Type) # make it possible to use W_List[W_Type]

# DispatchKind is a property of an OPERATOR and can be:
#
#   - 'single' if the opimpl depends only on the type of the first operand
#     (e.g., CALL, GETATTR, etc.)
#
#   - 'multi' is the opimpl depends on the types of all operands (e.g., all
#     binary operators)
DispatchKind = Literal['single', 'multi']

def maybe_blue(*colors: Color) -> Color:
    """
    Return 'blue' if all the given colors are blue, else 'red'
    """
    if set(colors) == {'blue'}:
        return 'blue'
    else:
        return 'red'


class TypeChecker:
    vm: 'SPyVM'
    w_func: W_ASTFunc
    funcef: ast.FuncDef
    expr_types: dict[ast.Expr, tuple[Color, W_Type]]
    expr_conv: dict[ast.Expr, TypeConverter]
    opimpl: dict[ast.Node, W_OpImpl]
    locals_types_w: dict[str, W_Type]


    def __init__(self, vm: 'SPyVM', w_func: W_ASTFunc) -> None:
        self.vm = vm
        self.w_func = w_func
        self.funcdef = w_func.funcdef
        self.expr_types = {}
        self.expr_conv = {}
        self.opimpl = {}
        self.locals_types_w = {}
        self.declare_arguments()

    def declare_arguments(self) -> None:
        """
        Declare the local vars for the arguments and @return
        """
        w_functype = self.w_func.w_functype
        self.declare_local('@return', w_functype.w_restype)
        params = self.w_func.w_functype.params
        for param in params:
            self.declare_local(param.name, param.w_type)

    def declare_local(self, name: str, w_type: W_Type) -> None:
        assert name not in self.locals_types_w, \
            f'variable already declared: {name}'
        self.locals_types_w[name] = w_type

    def typecheck_local(self, expr: ast.Expr, name: str) -> None:
        assert name in self.locals_types_w
        got_color, w_got_type = self.check_expr(expr)
        w_exp_type = self.locals_types_w[name]
        err = self.convert_type_maybe(expr, w_got_type, w_exp_type)
        if err is None:
            return
        #
        # we got a SPyTypeError, raise it
        exp = w_exp_type.name
        exp_loc = self.funcdef.symtable.lookup(name).type_loc
        if name == '@return':
            because = 'because of return type'
        else:
            because = 'because of type declaration'
        err.add('note', f'expected `{exp}` {because}', loc=exp_loc)
        raise err

    def typecheck_bool(self, expr: ast.Expr) -> None:
        color, w_type = self.check_expr(expr)
        err = self.convert_type_maybe(expr, w_type, B.w_bool)
        if err:
            msg = 'implicit conversion to `bool` is not implemented yet'
            err.add('note', msg, expr.loc)
            raise err

    def convert_type_maybe(self, expr: Optional[ast.Expr], w_got: W_Type,
                           w_exp: W_Type) -> Optional[SPyTypeError]:
        """
        Check that the given type if compatible with the expected type and/or can
        be converted to it.

        We have two cases, depending whether `expr` is None or not:

        1. `expr is not None`: this is the standard case, and the type comes
           from a user expression: in this case, automatic conversion is
           allowed

        2. `expr is None`: this happens only for a few builtin operators
           (e.g. the `attr` value in GETATTR/SETATTR): in this case, the types
           must match without conversions. It is an internal error to do
           otherwise.

        If there is a type mismatch, it returns a SPyTypeError: in that case,
        it is up to the caller to add extra info and raise the error.

        If the conversion can be made, return None.
        """
        if self.vm.issubclass(w_got, w_exp):
            # nothing to do
            return None

        # the types don't match and/or we need a conversion (see point 2 above)
        assert expr is not None

        # try to see whether we can apply a type conversion
        if self.vm.issubclass(w_exp, w_got):
            # implicit upcast
            self.expr_conv[expr] = DynamicCast(w_exp)
            return None
        elif w_got is B.w_i32 and w_exp is B.w_f64:
            # numeric conversion
            self.expr_conv[expr] = NumericConv(w_type=w_exp, w_fromtype=w_got)
            return None
        elif w_exp is JSFFI.w_JsRef and w_got in (B.w_str, B.w_i32):
            self.expr_conv[expr] = JsRefConv(w_type=JSFFI.w_JsRef,
                                             w_fromtype=w_got)
            return None
        elif w_exp is JSFFI.w_JsRef and isinstance(w_got, W_FuncType):
            assert w_got == W_FuncType.parse('def() -> void')
            self.expr_conv[expr] = JsRefConv(w_type=JSFFI.w_JsRef,
                                             w_fromtype=w_got)
            return None

        # mismatched types
        err = SPyTypeError('mismatched types')
        got = w_got.name
        exp = w_exp.name
        err.add('error', f'expected `{exp}`, got `{got}`', loc=expr.loc)
        return err

    def name2sym_maybe(self, expr: ast.Expr) -> Optional[Symbol]:
        """
        If expr is an ast.Name, return the corresponding Symbol.
        Else, return None.
        """
        if isinstance(expr, ast.Name):
            return self.funcdef.symtable.lookup_maybe(expr.id)
        return None

    def check_stmt(self, stmt: ast.Stmt) -> None:
        magic_dispatch(self, 'check_stmt', stmt)

    def check_expr(self, expr: ast.Expr) -> tuple[Color, W_Type]:
        """
        Compute the STATIC type of the given expression
        """
        if expr in self.expr_types:
            return self.expr_types[expr]
        else:
            color, w_type = magic_dispatch(self, 'check_expr', expr)
            self.expr_types[expr] = color, w_type
            return color, w_type

    # ==== statements ====

    def check_stmt_Return(self, ret: ast.Return) -> None:
        self.typecheck_local(ret.value, '@return')

    def check_stmt_Pass(self, stmt: ast.Pass) -> None:
        pass

    def check_stmt_VarDef(self, vardef: ast.VarDef) -> None:
        """
        VarDef is type-checked lazily, because the type annotation is evaluated
        at runtime.

        So, this function does nothing, and astframe calls lazy_check_VarDef
        after having evaluated the annotation. Similarly for
        lazy_check_FuncDef.
        """

    def lazy_check_VarDef(self, vardef: ast.VarDef, w_type: W_Type) -> None:
        self.declare_local(vardef.name, w_type)

    def check_stmt_FuncDef(self, funcdef: ast.FuncDef) -> None:
        """
        See check_stmt_VarDef
        """

    def lazy_check_FuncDef(self, funcdef: ast.FuncDef, w_type: W_Type) -> None:
        """
        See check_stmt_VarDef and lazy_check_VarDef
        """
        self.declare_local(funcdef.name, w_type)

    def check_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> None:
        pass

    def check_stmt_If(self, if_node: ast.If) -> None:
        self.typecheck_bool(if_node.test)

    def check_stmt_While(self, while_node: ast.While) -> None:
        self.typecheck_bool(while_node.test)

    def _check_assign(self, target: str, target_loc: Loc,
                      expr: ast.Expr) -> None:
        sym = self.funcdef.symtable.lookup(target)
        if sym.is_global and sym.color == 'blue':
            err = SPyTypeError("invalid assignment target")
            err.add('error', f'{sym.name} is const', target_loc)
            err.add('note', 'const declared here', sym.loc)
            err.add('note',
                    f'help: declare it as variable: `var {sym.name} ...`',
                    sym.loc)
            raise err

        if sym.is_local:
            if target not in self.locals_types_w:
                # first assignment, implicit declaration
                _, w_valuetype = self.check_expr(expr)
                self.declare_local(target, w_valuetype)
            self.typecheck_local(expr, target)

    def check_stmt_Assign(self, assign: ast.Assign) -> None:
        _, w_valuetype = self.check_expr(assign.value)
        self._check_assign(assign.target, assign.target_loc, assign.value)

    def check_stmt_UnpackAssign(self, unpack: ast.UnpackAssign) -> None:
        _, w_valuetype = self.check_expr(unpack.value)
        if w_valuetype is not B.w_tuple:
            t = w_valuetype.name
            err = SPyTypeError(f'`{t}` does not support unpacking')
            err.add('error', f'this is `{t}`', unpack.value.loc)
            raise err

        for i, (target, target_loc) in enumerate(unpack.targlocs):
            # we need an expression which has the type of each individual item
            # of the tuple. The easiest way is to synthetize a GetItem
            expr = ast.GetItem(
                loc = unpack.value.loc,
                value = unpack.value,
                index = ast.Constant(
                    loc = unpack.value.loc,
                    value = i
                )
            )
            self._check_assign(target, target_loc, expr)

    def check_stmt_SetAttr(self, node: ast.SetAttr) -> None:
        _, w_otype = self.check_expr(node.target)
        _, w_vtype = self.check_expr(node.value)
        w_attr = self.vm.wrap(node.attr)
        w_opimpl = self.vm.call_OP(OP.w_SETATTR, [w_otype, w_attr, w_vtype])
        errmsg = ("type `{0}` does not support assignment to attribute '%s'" %
                  node.attr)
        self.opimpl_typecheck(
            w_opimpl,
            node,
            [node.target, None, node.value],
            [w_otype, B.w_str, w_vtype],
            dispatch = 'single',
            errmsg = errmsg
        )
        self.opimpl[node] = w_opimpl

    def check_stmt_SetItem(self, node: ast.SetItem) -> None:
        self.OP_dispatch(
            OP.w_SETITEM,
            node,
            [node.target, node.index, node.value],
            dispatch = 'single',
            errmsg = "cannot do `{0}[`{1}`] = ..."
        )

    # ==== expressions ====

    def check_expr_Name(self, name: ast.Name) -> tuple[Color, W_Type]:
        varname = name.id
        sym = self.funcdef.symtable.lookup_maybe(varname)
        if sym is None:
            msg = f"name `{name.id}` is not defined"
            raise SPyNameError.simple(msg, "not found in this scope", name.loc)
        elif sym.fqn:
            # XXX this is wrong: we should keep track of the static type of
            # FQNs. For now, we just look it up and use the dynamic type
            w_value = self.vm.lookup_global(sym.fqn)
            assert w_value is not None
            return sym.color, self.vm.dynamic_type(w_value)
        elif sym.is_local:
            return sym.color, self.locals_types_w[name.id]
        else:
            # closed-over variables are always blue
            namespace = self.w_func.closure[sym.level]
            w_value = namespace[sym.name]
            assert w_value is not None
            return 'blue', self.vm.dynamic_type(w_value)

    def check_expr_Constant(self, const: ast.Constant) -> tuple[Color, W_Type]:
        T = type(const.value)
        assert T in (int, float, bool, str, NoneType)
        if T is int:
            return 'blue', B.w_i32
        elif T is float:
            return 'blue', B.w_f64
        elif T is bool:
            return 'blue', B.w_bool
        elif T is str:
            return 'blue', B.w_str
        elif T is NoneType:
            return 'blue', B.w_void
        assert False

    def check_expr_FQNConst(self, const: ast.FQNConst) -> tuple[Color, W_Type]:
        # XXX: I think that FQNConst should remember what was its static type
        w_val = self.vm.lookup_global(const.fqn)
        assert w_val is not None
        w_type = self.vm.dynamic_type(w_val)
        return 'blue', w_type

    def check_expr_BinOp(self, binop: ast.BinOp) -> tuple[Color, W_Type]:
        w_OP = OP.from_token(binop.op) # e.g., w_ADD, w_MUL, etc.
        return self.OP_dispatch(
            w_OP,
            binop,
            [binop.left, binop.right],
            dispatch = 'multi',
            errmsg = 'cannot do `{0}` %s `{1}`' % binop.op
        )

    check_expr_Add = check_expr_BinOp
    check_expr_Sub = check_expr_BinOp
    check_expr_Mul = check_expr_BinOp
    check_expr_Div = check_expr_BinOp
    check_expr_Eq = check_expr_BinOp
    check_expr_NotEq = check_expr_BinOp
    check_expr_Lt = check_expr_BinOp
    check_expr_LtE = check_expr_BinOp
    check_expr_Gt = check_expr_BinOp
    check_expr_GtE = check_expr_BinOp

    def check_expr_GetItem(self, expr: ast.GetItem) -> tuple[Color, W_Type]:
        c1, w_valtype = self.check_expr(expr.value)
        c2, w_itype = self.check_expr(expr.index)
        color = maybe_blue(c1, c2)
        wav_val = self.vm.new_absval('v', 0, w_valtype, expr.value.loc)
        wav_i = self.vm.new_absval('i', 1, w_itype, expr.index.loc)
        w_opimpl = self.vm.call_OP(OP.w_GETITEM, [wav_val, wav_i])
        self.opimpl[expr] = w_opimpl
        return color, w_opimpl.w_restype

    def check_expr_GetAttr(self, expr: ast.GetAttr) -> tuple[Color, W_Type]:
        color, w_vtype = self.check_expr(expr.value)
        w_attr = self.vm.wrap(expr.attr)
        w_opimpl = self.vm.call_OP(OP.w_GETATTR, [w_vtype, w_attr])
        self.opimpl_typecheck(
            w_opimpl,
            expr,
            [expr.value, None],
            [w_vtype, B.w_str],
            dispatch = 'single',
            errmsg = "type `{0}` has no attribute '%s'" % expr.attr
        )
        self.opimpl[expr] = w_opimpl
        return color, w_opimpl.w_restype

    def OP_dispatch(self, w_OP: Any, node: ast.Node, args: list[ast.Expr],
                    *,
                    dispatch: DispatchKind,
                    errmsg: str
                    ) -> tuple[Color, W_Type]:
        """
        Resolve and typecheck an operator call.

        It does the following:

          - typecheck the args and compute their type
          - call OP and get the opimpl
          - raise SPyTypeError if the opimpl is NotImplemented
          - check that the returned opimpl is compatible with the type of the
            args
          - record the opimpl for the given node

        Note that this works only for "regular" operators which operate only
        on argtypes. In particular, GETATTR and SETATTR needs to be handled
        differently, because they also take a VALUE (the attribute, as a
        string) instead of a TYPE.
        """
        if w_OP.qn.attr == 'GETITEM':
            return self.OP_dispatch_newstyle(w_OP, node, args,
                                             dispatch=dispatch,
                                             errmsg=errmsg)
        # step 1: determine the arguments to pass to OP()
        argtypes_w = []
        color: Color = 'blue'
        for arg in args:
            c1, w_argtype = self.check_expr(arg)
            argtypes_w.append(w_argtype)
            color = maybe_blue(color, c1)

        # step 2: call OP() and get w_opimpl
        assert w_OP.color == 'blue', f'{w_OP.qn} is not blue'
        w_opimpl = self.vm.call_OP(w_OP, argtypes_w) # type: ignore

        # step 3: check that we can call the returned w_opimpl
        self.opimpl_typecheck(w_opimpl, node, args, argtypes_w,
                              dispatch=dispatch, errmsg=errmsg)
        self.opimpl[node] = w_opimpl
        return color, w_opimpl.w_restype

    def OP_dispatch_newstyle(self, w_OP: Any, node: ast.Node,
                             args: list[ast.Expr],
                             *,
                             dispatch: DispatchKind,
                             errmsg: str
                             ) -> tuple[Color, W_Type]:
        # step 1: determine the arguments to pass to OP()
        args_wav: list[W_AbsVal] = []
        color: Color = 'blue'
        for i, arg in enumerate(args):
            c1, w_argtype = self.check_expr(arg)
            args_wav.append(self.vm.new_absval('v', i, w_argtype, arg.loc))
            color = maybe_blue(color, c1)

        # step 2: call OP() and get w_opimpl
        assert w_OP.color == 'blue', f'{w_OP.qn} is not blue'
        w_opimpl = self.vm.call_OP(w_OP, args_wav) # type: ignore

        # step 3: check that we can call the returned w_opimpl
        if w_opimpl._args_wav is None:
            # XXX this is a temporary hack: in this case, what we want to do
            # is to create "default" AbsVals and just pass them around. But we
            # cannot because there are still operators using the old-style
            # dispatch and they expect argtypes_w.
            argtypes_w = [wav.w_static_type for wav in args_wav]
        else:
            argtypes_w = [wav.w_static_type for wav in w_opimpl._args_wav]
        self.opimpl_typecheck(w_opimpl, node, args, argtypes_w,
                              dispatch=dispatch, errmsg=errmsg)
        self.opimpl[node] = w_opimpl
        return color, w_opimpl.w_restype


    def opimpl_typecheck(self,
                         w_opimpl: W_OpImpl,
                         node: ast.Node,
                         args: Sequence[ast.Expr | None],
                         argtypes_w: list[W_Type],
                         *,
                         dispatch: DispatchKind,
                         errmsg: str,
                         ) -> None:
        """
        Check the arg types that we are passing to the opimpl, and insert
        appropriate type conversions if needed.

        `dispatch` is used only for diagnostics: if it's 'single' we will
        report the type of the first operand, else of all operands.
        """
        if w_opimpl.is_null():
            typenames = [w_t.name for w_t in argtypes_w]
            errmsg = errmsg.format(*typenames)
            err = SPyTypeError(errmsg)
            if dispatch == 'single':
                # for single dispatch ops, NotImplemented means that the
                # target doesn't support this operation: so we just report its
                # type and possibly its definition
                assert args[0] is not None
                target = args[0]
                t = argtypes_w[0].name
                err.add('error', f'this is `{t}`', target.loc)
                sym = self.name2sym_maybe(target)
                if sym:
                    assert isinstance(target, ast.Name)
                    err.add('note', f'`{target.id}` defined here', sym.loc)
            else:
                # for multi dispatch ops, all operands are equally important
                # for finding the opimpl: we report all of them
                for arg, w_argtype in zip(args, argtypes_w):
                    if arg is not None:
                        t = w_argtype.name
                        err.add('error', f'this is `{t}`', arg.loc)
            raise err

        w_functype = w_opimpl.w_func.w_functype

        self.call_typecheck(
            w_functype,
            argtypes_w,
            def_loc = None, # would be nice to find it somehow
            call_loc = node.loc, # type: ignore
            argnodes = args)

    def check_expr_Call(self, call: ast.Call) -> tuple[Color, W_Type]:
        color, w_otype = self.check_expr(call.func)
        if w_otype is B.w_dynamic:
            # XXX: how are we supposed to know the color of the result if we
            # are calling a dynamic expr?
            # E.g.:
            #
            # @blue
            # def foo(): ...
            #
            # @blue
            # def bar(): ...
            #     x: dynamic = foo
            #     x()   # color???
            return 'red', B.w_dynamic # ???
        elif isinstance(w_otype, W_FuncType):
            # direct call to a function, let's typecheck it directly
            return self._check_expr_call_func(call)
        else:
            # generic call to an arbitrary object, try to use op.CALL
            return self._check_expr_call_generic(call)

    def _check_expr_call_func(self, call: ast.Call) -> tuple[Color, W_Type]:
        color, w_functype = self.check_expr(call.func)
        assert isinstance(w_functype, W_FuncType)
        argtypes_w = [self.check_expr(arg)[1] for arg in call.args]
        call_loc = call.func.loc
        sym = self.name2sym_maybe(call.func)
        def_loc = sym.loc if sym else None
        self.call_typecheck(
            w_functype,
            argtypes_w,
            def_loc = def_loc,
            call_loc = call_loc,
            argnodes = call.args)
        # the color of the result depends on the color of the function: if
        # we call a @blue function, we get a blue result
        rescolor = w_functype.color
        return rescolor, w_functype.w_restype

    def _check_expr_call_generic(self, call: ast.Call) -> tuple[Color, W_Type]:
        _, w_otype = self.check_expr(call.func)
        argtypes_w = [self.check_expr(arg)[1] for arg in call.args]
        w_argtypes = W_List[W_Type](argtypes_w) # type: ignore
        w_opimpl = self.vm.call_OP(OP.w_CALL, [w_otype, w_argtypes])
        newargs = [call.func] + call.args
        errmsg = 'cannot call objects of type `{0}`'
        self.opimpl_typecheck(w_opimpl, call, newargs,
                              [w_otype] + argtypes_w,
                              dispatch='single',
                              errmsg=errmsg)
        self.opimpl[call] = w_opimpl
        # XXX I'm not sure that the color is correct here. We need to think
        # more.
        w_functype = w_opimpl.w_func.w_functype
        return w_functype.color, w_functype.w_restype

    def call_typecheck(self,
                       w_functype: W_FuncType,
                       argtypes_w: Sequence[W_Type],
                       *,
                       def_loc: Optional[Loc],
                       call_loc: Optional[Loc],
                       argnodes: Sequence[ast.Expr | None],
                       ) -> None:
        got_nargs = len(argtypes_w)
        exp_nargs = len(w_functype.params)
        if got_nargs != exp_nargs:
            self._call_error_wrong_argcount(
                got_nargs,
                exp_nargs,
                def_loc = def_loc,
                call_loc = call_loc,
                argnodes = argnodes)
        #
        assert len(argnodes) == len(argtypes_w)
        for i, (param, w_arg_type) in enumerate(zip(w_functype.params,
                                                    argtypes_w)):
            arg_expr = argnodes[i]
            err = self.convert_type_maybe(arg_expr, w_arg_type, param.w_type)
            if err:
                if def_loc:
                    err.add('note', 'function defined here', def_loc)
                raise err

    def _call_error_wrong_argcount(self, got: int, exp: int,
                                   *,
                                   def_loc: Optional[Loc],
                                   call_loc: Optional[Loc],
                                   argnodes: Sequence[ast.Expr | None],
                                   ) -> NoReturn:
        assert got != exp
        takes = maybe_plural(exp, f'takes {exp} argument')
        supplied = maybe_plural(got,
                                f'1 argument was supplied',
                                f'{got} arguments were supplied')
        err = SPyTypeError(f'this function {takes} but {supplied}')
        #
        # if we know the call_loc, we can add more detailed errors
        if call_loc:
            assert argnodes is not None
            if got < exp:
                diff = exp - got
                arguments = maybe_plural(diff, 'argument')
                err.add('error', f'{diff} {arguments} missing', call_loc)
            else:
                diff = got - exp
                arguments = maybe_plural(diff, 'argument')
                first_extra_arg = argnodes[exp]
                last_extra_arg = argnodes[-1]
                assert first_extra_arg is not None
                assert last_extra_arg is not None
                # XXX this assumes that all the arguments are on the same line
                loc = first_extra_arg.loc.replace(
                    col_end = last_extra_arg.loc.col_end
                )
                err.add('error', f'{diff} extra {arguments}', loc)
        #
        if def_loc:
            err.add('note', 'function defined here', def_loc)
        raise err

    def check_expr_CallMethod(self, op: ast.CallMethod) -> tuple[Color, W_Type]:
        _, w_otype = self.check_expr(op.target)
        w_method = self.vm.wrap(op.method)
        argtypes_w = [self.check_expr(arg)[1] for arg in op.args]
        w_argtypes = W_List[W_Type](argtypes_w) # type: ignore
        w_opimpl = self.vm.call_OP(OP.w_CALL_METHOD,
                                   [w_otype, w_method, w_argtypes])
        w_method = self.vm.wrap(op.method)
        m = ast.Constant(op.loc, value=w_method)
        newargs = [op.target, m] + op.args
        errmsg = 'cannot call methods on type `{0}`'
        self.opimpl_typecheck(w_opimpl, op, newargs,
                              [w_otype, B.w_str] + argtypes_w,
                              dispatch='single',
                              errmsg=errmsg)
        self.opimpl[op] = w_opimpl
        # XXX I'm not sure that the color is correct here. We need to think
        # more.
        w_functype = w_opimpl.w_func.w_functype
        return w_functype.color, w_functype.w_restype

    def check_expr_List(self, listop: ast.List) -> tuple[Color, W_Type]:
        w_itemtype = None
        color: Color = 'red' # XXX should be blue?

        for item in listop.items:
            c1, w_t1 = self.check_expr(item)
            color = maybe_blue(color, c1)
            if w_itemtype is None:
                w_itemtype = w_t1
            w_itemtype = self.vm.union_type(w_itemtype, w_t1)
        #
        # XXX we need to handle empty lists
        assert w_itemtype is not None
        w_listtype = self.vm.make_list_type(w_itemtype)
        return color, w_listtype

    def check_expr_Tuple(self, tupleop: ast.Tuple) -> tuple[Color, W_Type]:
        color: Color = 'blue'
        for item in tupleop.items:
            c1, w_t1 = self.check_expr(item)
            color = maybe_blue(color, c1)
        return color, B.w_tuple




# ===== NEW STYLE TYPECHECKING =====
# A lot of this code is copied&pasted from TypeChecker for now.
# The goal is to kill the TypeChecker class eventually

def typecheck_opimpl(
        vm: 'SPyVM',
        w_opimpl: W_OpImpl,
        #node: ast.Node,
        args_wav: list[W_AbsVal],
        *,
        dispatch: DispatchKind,
        errmsg: str,
) -> None:
    if w_opimpl.is_null():
        typenames = [wav.w_static_type.name for wav in args_wav]
        errmsg = errmsg.format(*typenames)
        err = SPyTypeError(errmsg)
        if dispatch == 'single':
            # for single dispatch ops, NotImplemented means that the
            # target doesn't support this operation: so we just report its
            # type and possibly its definition
            #assert args[0] is not None
            wav_obj = args_wav[0]
            t = wav_obj.w_static_type.name
            if wav_obj.loc:
                err.add('error', f'this is `{t}`', wav_obj.loc)

            ## sym = self.name2sym_maybe(target)
            ## if sym:
            ##     assert isinstance(target, ast.Name)
            ##     err.add('note', f'`{target.id}` defined here', sym.loc)

        else:
            #XXX fixme

            # for multi dispatch ops, all operands are equally important
            # for finding the opimpl: we report all of them
            for arg, w_argtype in zip(args, argtypes_w):
                if arg is not None:
                    t = w_argtype.name
                    err.add('error', f'this is `{t}`', arg.loc)
        raise err

    w_functype = w_opimpl.w_func.w_functype

    typecheck_call(
        vm,
        w_functype,
        args_wav)
        ## def_loc = None, # would be nice to find it somehow
        ## call_loc = None), # XXX node.loc, # type: ignore


def typecheck_call(
        vm: 'SPyVM',
        w_functype: W_FuncType,
        args_wav: list[W_AbsVal],
        ## *,
        ## def_loc: Optional[Loc],
        ## call_loc: Optional[Loc],
) -> None:
    # XXX
    call_loc = None
    def_loc = None

    got_nargs = len(args_wav)
    exp_nargs = len(w_functype.params)
    if got_nargs != exp_nargs:
        _call_error_wrong_argcount(
            got_nargs,
            exp_nargs,
            args_wav,
            def_loc = def_loc,
            call_loc = call_loc)
    #
    # check that the types of the arguments are compatible
    for param, wav_arg in zip(w_functype.params, args_wav):
        # XXX: we need to find a way to re-enable implicit conversions
        err = convert_type_maybe(vm, wav_arg, param.w_type)
        if err:
            if def_loc:
                err.add('note', 'function defined here', def_loc)
            raise err


def convert_type_maybe(
        vm: 'SPyVM',
        wav_x: W_Type,
        w_exp: W_Type
) -> Optional[SPyTypeError]:
    w_got = wav_x.w_static_type
    if vm.issubclass(w_got, w_exp):
        # nothing to do
        return None

    # XXX IMPLEMENT ME
    # we need to re-enable implicit conversions

    err = SPyTypeError('mismatched types')
    got = w_got.name
    exp = w_exp.name
    err.add('error', f'expected `{exp}`, got `{got}`', loc=wav_x.loc)
    return err


def _call_error_wrong_argcount(
        got: int, exp: int,
        args_wav: list[W_AbsVal],
        *,
        def_loc: Optional[Loc],
        call_loc: Optional[Loc],
) -> NoReturn:
    assert got != exp
    takes = maybe_plural(exp, f'takes {exp} argument')
    supplied = maybe_plural(got,
                            f'1 argument was supplied',
                            f'{got} arguments were supplied')
    err = SPyTypeError(f'this function {takes} but {supplied}')
    #
    # if we know the call_loc, we can add more detailed errors
    if call_loc:
        assert argnodes is not None
        if got < exp:
            diff = exp - got
            arguments = maybe_plural(diff, 'argument')
            err.add('error', f'{diff} {arguments} missing', call_loc)
        else:
            diff = got - exp
            arguments = maybe_plural(diff, 'argument')
            first_extra_loc = args_wav[exp].loc
            last_extra_loc = args_wav[exp].loc
            assert first_extra_loc is not None
            assert last_extra_loc is not None
            # XXX this assumes that all the arguments are on the same line
            loc = first_extra_loc.replace(
                col_end = last_extra_loc.col_end
            )
            err.add('error', f'{diff} extra {arguments}', loc)
    #
    if def_loc:
        err.add('note', 'function defined here', def_loc)
    raise err
