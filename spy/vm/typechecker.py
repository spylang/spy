from typing import TYPE_CHECKING, Optional, NoReturn, Any
from types import NoneType
from spy import ast
from spy.fqn import QN, FQN
from spy.irgen.symtable import Symbol, Color
from spy.errors import (SPyTypeError, SPyNameError, maybe_plural)
from spy.location import Loc
from spy.vm.object import W_Object, W_Type
from spy.vm.list import make_W_List
from spy.vm.function import W_FuncType, W_ASTFunc, W_Func
from spy.vm.b import B
from spy.vm.modules.operator import OP
from spy.vm.typeconverter import TypeConverter, DynamicCast, NumericConv
from spy.vm.modules.types import W_TypeDef
from spy.util import magic_dispatch
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

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
    opimpl: dict[ast.Node, W_Func]
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

    def convert_type_maybe(self, expr: ast.Expr, w_got: W_Type,
                           w_exp: W_Type) -> Optional[SPyTypeError]:
        """
        Check that the given expr if compatible with the expected type and/or can
        be converted to it.

        If needed, it registers a type converter for the expr.

        If there is a type mismatch, it returns a SPyTypeError: in that case,
        it is up to the caller to add extra info and raise the error.

        If the conversion can be made, return None.
        """
        if self.vm.issubclass(w_got, w_exp):
            # nothing to do
            return None
        elif self.vm.issubclass(w_exp, w_got):
            # implicit upcast
            self.expr_conv[expr] = DynamicCast(w_exp)
            return None
        elif w_got is B.w_i32 and w_exp is B.w_f64:
            # numeric conversion
            self.expr_conv[expr] = NumericConv(w_type=w_exp, w_fromtype=w_got)
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

    def check_stmt_Assign(self, assign: ast.Assign) -> None:
        name = assign.target
        sym = self.funcdef.symtable.lookup(name)
        if sym.is_global and sym.color == 'blue':
            err = SPyTypeError("invalid assignment target")
            err.add('error', f'{sym.name} is const', assign.target_loc)
            err.add('note', 'const declared here', sym.loc)
            err.add('note',
                    f'help: declare it as variable: `var {sym.name} ...`',
                    sym.loc)
            raise err

        _, w_valuetype = self.check_expr(assign.value)

        if sym.is_local:
            if name not in self.locals_types_w:
                # first assignment, implicit declaration
                self.declare_local(name, w_valuetype)
            self.typecheck_local(assign.value, name)

    def check_stmt_SetAttr(self, node: ast.SetAttr) -> None:
        _, w_otype = self.check_expr(node.target)
        _, w_vtype = self.check_expr(node.value)

        w_attr = self.vm.wrap(node.attr)
        w_opimpl = OP.w_SETATTR.pyfunc(self.vm, w_otype, w_attr, w_vtype)
        if w_opimpl is B.w_NotImplemented:
            ot = w_otype.name
            vt = w_vtype.name
            attr = node.attr
            err = SPyTypeError(
                f"type `{ot}` does not support assignment to attribute '{attr}'")
            err.add('error', f'this is `{ot}`', node.target.loc)
            err.add('error', f'this is `{vt}`', node.value.loc)
            raise err
        else:
            self.opimpl[node] = w_opimpl

    def check_stmt_SetItem(self, node: ast.SetItem) -> None:
        _, w_otype = self.check_expr(node.target)
        _, w_itype = self.check_expr(node.index)
        _, w_vtype = self.check_expr(node.value)

        w_opimpl = OP.w_SETITEM.pyfunc(self.vm, w_otype, w_itype, w_vtype)
        if w_opimpl is B.w_NotImplemented:
            # XXX better error and write a test
            err = SPyTypeError("setitem not implemented")
            raise err
        else:
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
        lcolor, w_ltype = self.check_expr(binop.left)
        rcolor, w_rtype = self.check_expr(binop.right)
        color = maybe_blue(lcolor, rcolor)

        w_op = OP.from_token(binop.op) # e.g., w_ADD, w_MUL, etc.
        w_opimpl = self.vm.call_function(w_op, [w_ltype, w_rtype])

        if w_opimpl is B.w_NotImplemented:
            lt = w_ltype.name
            rt = w_rtype.name
            err = SPyTypeError(f'cannot do `{lt}` {binop.op} `{rt}`')
            err.add('error', f'this is `{lt}`', binop.left.loc)
            err.add('error', f'this is `{rt}`', binop.right.loc)
            raise err

        assert isinstance(w_opimpl, W_Func)
        self.opimpl_check_args(w_opimpl, binop, [binop.left, binop.right])
        self.opimpl[binop] = w_opimpl
        w_restype = w_opimpl.w_functype.w_restype
        return color, w_restype

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

    def opimpl_check_args(self, w_opimpl: W_Func, op: ast.Expr,
                          args: list[ast.Expr]) -> None:
        """
        Check that arg types that we are passing to the opimpl, and insert
        appropriate type conversions if needed.

        Note: this is very similar to check_call & co: the difference is
        that if here we find mistake in the signature (e.g. wrong argcount
        or type mismatch) we treat it as an internal error instead of an
        user error.

        Maybe we could reduce a bit the code duplication in the future.
        """
        w_functype = w_opimpl.w_functype
        argtypes_w = [self.check_expr(arg)[1] for arg in args]
        got_nargs = len(argtypes_w)
        exp_nargs = len(w_functype.params)
        assert got_nargs == exp_nargs, 'wrong opimpl?'

        for i, (param, w_arg_type) in enumerate(zip(w_functype.params,
                                                    argtypes_w)):
            err = self.convert_type_maybe(args[i], w_arg_type, param.w_type)
            assert not err, 'wrong opimpl?'

    def check_expr_GetItem(self, expr: ast.GetItem) -> tuple[Color, W_Type]:
        vcolor, w_vtype = self.check_expr(expr.value)
        icolor, w_itype = self.check_expr(expr.index)
        color = maybe_blue(vcolor, icolor)
        w_opimpl = OP.w_GETITEM.pyfunc(self.vm, w_vtype, w_itype)
        if (isinstance(w_opimpl, W_Func) and
            w_opimpl.qn == QN('operator::str_getitem')):
            # XXX for now this is a special case, to check that `i` can be
            # converted to `i32`. Ideally, we should use the same mechanism
            # that we have already for calls
            self.opimpl[expr] = w_opimpl
            err = self.convert_type_maybe(expr.index, w_itype, B.w_i32)
            if err:
                err.add('note', f'this is a `str`', expr.value.loc)
                raise err
            return color, B.w_str
        elif w_opimpl is not B.w_NotImplemented:
            # this should be merged with the 'then' above
            self.opimpl[expr] = w_opimpl
            return color, w_opimpl.w_functype.w_restype
        else:
            v = w_vtype.name
            i = w_itype.name
            err = SPyTypeError(f'cannot do `{v}`[`{i}`]')
            err.add('error', f'this is `{v}`', expr.value.loc)
            err.add('error', f'this is `{i}`', expr.index.loc)
            raise err

    def check_expr_GetAttr(self, expr: ast.GetAttr) -> tuple[Color, W_Type]:
        color, w_vtype = self.check_expr(expr.value)
        w_attr = self.vm.wrap(expr.attr)
        w_opimpl = OP.w_GETATTR.pyfunc(self.vm, w_vtype, w_attr)
        if w_opimpl is B.w_NotImplemented:
            v = w_vtype.name
            err = SPyTypeError(f"type `{v}` has no attribute '{expr.attr}'")
            err.add('error', f'this is `{v}`', expr.value.loc)
            raise err
        else:
            self.opimpl[expr] = w_opimpl
            return color, w_opimpl.w_functype.w_restype

    def check_expr_Call(self, call: ast.Call) -> tuple[Color, W_Type]:
        color, w_functype = self.check_expr(call.func)
        sym = self.name2sym_maybe(call.func)

        if w_functype is B.w_dynamic:
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

        if not isinstance(w_functype, W_FuncType):
            self._call_error_non_callable(call, sym, w_functype)
        #
        argtypes_w = [self.check_expr(arg)[1] for arg in call.args]
        got_nargs = len(argtypes_w)
        exp_nargs = len(w_functype.params)
        if got_nargs != exp_nargs:
            self._call_error_wrong_argcount(call, sym, got_nargs, exp_nargs)
        #
        for i, (param, w_arg_type) in enumerate(zip(w_functype.params,
                                                    argtypes_w)):
            err = self.convert_type_maybe(call.args[i], w_arg_type, param.w_type)
            if err:
                if sym:
                    err.add('note', 'function defined here', sym.loc)
                raise err
        #
        # the color of the result depends on the color of the function: if we
        # call a @blue function, we get a blue result
        rescolor = w_functype.color
        return rescolor, w_functype.w_restype

    def _call_error_non_callable(self, call: ast.Call,
                                 sym: Optional[Symbol],
                                 w_type: W_Type) -> NoReturn:
        err = SPyTypeError(f'cannot call objects of type `{w_type.name}`')
        err.add('error', 'this is not a function', call.func.loc)
        if sym:
            err.add('note', 'variable defined here', sym.loc)
        raise err

    def _call_error_wrong_argcount(self, call: ast.Call,
                                   sym: Optional[Symbol],
                                   got: int, exp: int) -> NoReturn:
        assert got != exp
        takes = maybe_plural(exp, f'takes {exp} argument')
        supplied = maybe_plural(got,
                                f'1 argument was supplied',
                                f'{got} arguments were supplied')
        err = SPyTypeError(f'this function {takes} but {supplied}')
        #
        if got < exp:
            diff = exp - got
            arguments = maybe_plural(diff, 'argument')
            err.add('error', f'{diff} {arguments} missing', call.func.loc)
        else:
            diff = got - exp
            arguments = maybe_plural(diff, 'argument')
            first_extra_arg = call.args[exp]
            last_extra_arg = call.args[-1]
            # XXX this assumes that all the arguments are on the same line
            loc = first_extra_arg.loc.replace(
                col_end = last_extra_arg.loc.col_end
            )
            err.add('error', f'{diff} extra {arguments}', loc)
        #
        if sym:
            err.add('note', 'function defined here', sym.loc)
        raise err

    def check_expr_List(self, listop: ast.List) -> tuple[Color, W_Type]:
        w_itemtype = None
        color: Color = 'red' # XXX should be blue?
        for item in listop.items:
            c1, w_t1 = self.check_expr(item)
            color = maybe_blue(color, c1)
            if w_itemtype is None:
                w_itemtype = w_t1
            elif w_itemtype is not w_t1:
                # XXX write it better and write a test
                err = SPyTypeError("conflicting item types")
                raise err
        #
        # XXX we need to handle empty lists
        assert w_itemtype is not None
        w_listype = make_W_List(self.vm, w_itemtype)
        return color, w_listype
