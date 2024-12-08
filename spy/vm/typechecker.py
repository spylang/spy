from typing import TYPE_CHECKING, Optional, NoReturn, Any, Sequence, Literal
from types import NoneType
from spy import ast
from spy.irgen.symtable import Symbol, Color
from spy.errors import (SPyTypeError, SPyNameError, maybe_plural)
from spy.location import Loc
from spy.vm.modules.operator.convop import CONVERT_maybe
from spy.vm.object import W_Object, W_Type
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.function import W_ASTFunc, W_Func
from spy.vm.b import B
from spy.vm.modules.operator import OP, OP_from_token
from spy.vm.modules.types import W_TypeDef
from spy.util import magic_dispatch
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

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
    expr_conv: dict[ast.Expr, W_Func]
    opimpl: dict[ast.Node, W_OpImpl]
    locals_types_w: dict[str, W_Type]


    def __init__(self, vm: 'SPyVM', w_func: W_ASTFunc) -> None:
        self.vm = vm
        self.w_func = w_func
        self.funcdef = w_func.funcdef
        self.expr_types = {}
        # XXX: expr_conv nowadays is used only for typechecking locals. Maybe
        # we should use a better system?
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

        wop_local = W_OpArg('v', 0, w_got_type, expr.loc)
        try:
            w_conv = CONVERT_maybe(self.vm, w_exp_type, wop_local)
            if w_conv is not None:
                self.expr_conv[expr] = w_conv
        except SPyTypeError as err:
            exp = w_exp_type.fqn.human_name
            exp_loc = self.funcdef.symtable.lookup(name).type_loc
            if name == '@return':
                because = 'because of return type'
            else:
                because = 'because of type declaration'
            err.add('note', f'expected `{exp}` {because}', loc=exp_loc)
            raise

    def typecheck_bool(self, expr: ast.Expr) -> None:
        color, w_got_type = self.check_expr(expr)
        wop_cond = W_OpArg('v', 0, w_got_type, expr.loc)
        try:
            w_conv = CONVERT_maybe(self.vm, B.w_bool, wop_cond)
            if w_conv is not None:
                self.expr_conv[expr] = w_conv
        except SPyTypeError as err:
            msg = 'implicit conversion to `bool` is not implemented yet'
            err.add('note', msg, expr.loc)
            raise

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

    def check_many_exprs(self,
                         prefixes: list[str],
                         exprs: Sequence[ast.Expr | str]
                         ) -> tuple[list[Color], list[W_OpArg]]:
        assert len(prefixes) == len(exprs)
        colors = []
        args_wop = []
        last_loc = None
        for i, (prefix, expr) in enumerate(zip(prefixes, exprs)):
            if isinstance(expr, str):
                # HACK HACK HACK: we need a loc but we don't have any. We just
                # use the last_loc. This works only as far as this doesn't
                # happen at the first iteration, which is good enough in
                # practice.
                #
                # Ultimately this happens because astr.GetAttr.attr is of type
                # 'str'. Probably we should just turn it into a "real" Expr,
                # so that it will be automatically and transparetly converted
                # into a W_OpArg
                assert last_loc is not None
                loc = last_loc
                color = 'blue'
                wop = W_OpArg(prefix, i, B.w_str, loc,
                             w_blueval = self.vm.wrap(expr))
            else:
                color, w_type = self.check_expr(expr)
                wop = W_OpArg(prefix, i, w_type, expr.loc,
                             sym=self.name2sym_maybe(expr))
                last_loc = expr.loc
            colors.append(color)
            args_wop.append(wop)
        return colors, args_wop

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

    def check_stmt_ClassDef(self, classdef: ast.ClassDef) -> None:
        """
        See check_stmt_VarDef
        """

    def lazy_check_ClassDef(self, classdef: ast.ClassDef,
                            w_type: W_Type) -> None:
        """
        See check_stmt_ClassDef and lazy_check_ClassDef
        """
        self.declare_local(classdef.name, w_type)

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
            t = w_valuetype.fqn.human_name
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
        _, args_wop = self.check_many_exprs(
            ['t', 'a', 'v'],
            [node.target, node.attr, node.value]
        )
        w_opimpl = self.vm.call_OP(OP.w_SETATTR, args_wop)
        self.opimpl[node] = w_opimpl

    def check_stmt_SetItem(self, node: ast.SetItem) -> None:
        _, args_wop = self.check_many_exprs(
            ['t', 'i', 'v'],
            [node.target, node.index, node.value]
        )
        w_opimpl = self.vm.call_OP(OP.w_SETITEM, args_wop)
        self.opimpl[node] = w_opimpl

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
        w_OP = OP_from_token(binop.op) # e.g., w_ADD, w_MUL, etc.
        colors, args_wop = self.check_many_exprs(
            ['l', 'r'],
            [binop.left, binop.right],
        )
        color = maybe_blue(*colors)
        w_opimpl = self.vm.call_OP(w_OP, args_wop)
        self.opimpl[binop] = w_opimpl
        return color, w_opimpl.w_restype

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
        colors, args_wop = self.check_many_exprs(
            ['v', 'i'],
            [expr.value, expr.index],
        )
        color = maybe_blue(*colors)
        w_opimpl = self.vm.call_OP(OP.w_GETITEM, args_wop)
        self.opimpl[expr] = w_opimpl
        return color, w_opimpl.w_restype

    def check_expr_GetAttr(self, expr: ast.GetAttr) -> tuple[Color, W_Type]:
        colors, args_wop = self.check_many_exprs(
            ['v', 'a'],
            [expr.value, expr.attr]
        )
        w_opimpl = self.vm.call_OP(OP.w_GETATTR, args_wop)
        self.opimpl[expr] = w_opimpl
        return colors[0], w_opimpl.w_restype

    def check_expr_Call(self, call: ast.Call) -> tuple[Color, W_Type]:
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
        #
        # So far we always return red, because callop._dynamic_call_opimpl
        # returns a w_functype of red color. But we need to think whether this
        # is the real behavior that we want.

        n = len(call.args)
        colors, args_wop = self.check_many_exprs(
            ['f'] + ['v']*n,
            [call.func] + call.args
        )
        w_opimpl = self.vm.call_OP(OP.w_CALL, args_wop)
        self.opimpl[call] = w_opimpl
        w_functype = w_opimpl.w_functype
        return w_functype.color, w_functype.w_restype

    def check_expr_CallMethod(self, op: ast.CallMethod) -> tuple[Color, W_Type]:
        n = len(op.args)
        colors, args_wop = self.check_many_exprs(
            ['t', 'm'] + ['v']*n,
            [op.target, op.method] + op.args  # type: ignore
        )
        w_opimpl = self.vm.call_OP(OP.w_CALL_METHOD, args_wop)
        self.opimpl[op] = w_opimpl
        w_functype = w_opimpl.w_functype
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
        orig_args_wop: list[W_OpArg],
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
        # this means that we couldn't find an OpImpl for this OPERATOR.
        # The details of the error message depends on the DispatchKind:

        #  - single dispatch means that the target (argument 0) doesn't
        #    support this operation, so we report its type and its definition
        #
        #  - multi dispatch means that all the types are equally imporant in
        #    determining whether an operation is supported, so we report all
        #    of them
        typenames = [wop.w_static_type.fqn.human_name for wop in orig_args_wop]
        errmsg = errmsg.format(*typenames)
        err = SPyTypeError(errmsg)
        if dispatch == 'single':
            wop_target = orig_args_wop[0]
            t = wop_target.w_static_type.fqn.human_name
            if wop_target.loc:
                err.add('error', f'this is `{t}`', wop_target.loc)
            if wop_target.sym:
                sym = wop_target.sym
                err.add('note', f'`{sym.name}` defined here', sym.loc)
        else:
            for wop_arg in orig_args_wop:
                t = wop_arg.w_static_type.fqn.human_name
                err.add('error', f'this is `{t}`', wop_arg.loc)
        raise err

    # if it's a simple OpImpl, we automatically pass the orig_args_wop in order
    if w_opimpl.is_simple():
        w_opimpl.set_args_wop(orig_args_wop)
    args_wop = w_opimpl._args_wop
    assert args_wop is not None

    # if it's a direct call, we can get extra info about call and def locations
    call_loc = None
    def_loc = None
    if w_opimpl.is_direct_call():
        wop_func = orig_args_wop[0]
        call_loc = wop_func.loc
        # not all direct calls targets have a sym (e.g. if we call a builtin)
        if wop_func.sym is not None:
            def_loc = wop_func.sym.loc

    # check that the number of arguments match
    w_functype = w_opimpl.w_functype
    got_nargs = len(args_wop)
    exp_nargs = len(w_functype.params)

    if w_functype.is_varargs:
        argcount_ok = got_nargs >= exp_nargs
    else:
        argcount_ok = got_nargs == exp_nargs

    if not argcount_ok:
        _call_error_wrong_argcount(
            got_nargs,
            exp_nargs,
            args_wop,
            def_loc = def_loc,
            call_loc = call_loc)

    # check that the types of the arguments are compatible
    assert w_opimpl._converters_w is not None
    for i, (param, wop_arg) in enumerate(zip(w_functype.params, args_wop)):
        try:
            w_conv = CONVERT_maybe(vm, param.w_type, wop_arg)
            w_opimpl._converters_w[i] = w_conv
        except SPyTypeError as err:
            if def_loc:
                err.add('note', 'function defined here', def_loc)
            raise

    # everything good!
    w_opimpl._typechecked = True

def _call_error_wrong_argcount(
        got: int, exp: int,
        args_wop: list[W_OpArg],
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
        if got < exp:
            diff = exp - got
            arguments = maybe_plural(diff, 'argument')
            err.add('error', f'{diff} {arguments} missing', call_loc)
        else:
            diff = got - exp
            arguments = maybe_plural(diff, 'argument')
            first_extra_loc = args_wop[exp].loc
            last_extra_loc = args_wop[-1].loc
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
