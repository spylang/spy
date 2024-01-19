from typing import TYPE_CHECKING, Optional, NoReturn
from types import NoneType
from spy import ast
from spy.fqn import FQN
from spy.irgen.symtable import Symbol, Color
from spy.errors import (SPyTypeError, SPyNameError, maybe_plural)
from spy.location import Loc
from spy.vm.object import W_Object, W_Type
from spy.vm.function import W_FuncType, W_ASTFunc
from spy.vm.builtins import B
from spy.vm import helpers
from spy.vm.typeconverter import TypeConverter, DynamicCast
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
    locals_types_w: dict[str, W_Type]


    def __init__(self, vm: 'SPyVM', w_func: W_ASTFunc) -> None:
        self.vm = vm
        self.w_func = w_func
        self.funcdef = w_func.funcdef
        self.expr_types = {}
        self.expr_conv = {}
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
            #assert sym.color == 'blue' # XXX this fails?
            namespace = self.w_func.closure[sym.level]
            w_value = namespace[sym.name]
            assert w_value is not None
            return sym.color, self.vm.dynamic_type(w_value)

    def check_expr_Constant(self, const: ast.Constant) -> tuple[Color, W_Type]:
        T = type(const.value)
        assert T in (int, bool, str, NoneType)
        if T is int:
            return 'blue', B.w_i32
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
        if w_ltype is w_rtype is B.w_i32:
            return color, B.w_i32
        if binop.op == '+' and w_ltype is w_rtype is B.w_str:
            return color, B.w_str
        if binop.op == '*' and w_ltype is B.w_str and w_rtype is B.w_i32:
            return color, B.w_str
        #
        lt = w_ltype.name
        rt = w_rtype.name
        err = SPyTypeError(f'cannot do `{lt}` {binop.op} `{rt}`')
        err.add('error', f'this is `{lt}`', binop.left.loc)
        err.add('error', f'this is `{rt}`', binop.right.loc)
        raise err

    check_expr_Add = check_expr_BinOp
    check_expr_Mul = check_expr_BinOp

    def check_expr_CompareOp(self, op: ast.CompareOp) -> tuple[Color, W_Type]:
        lcolor, w_ltype = self.check_expr(op.left)
        rcolor, w_rtype = self.check_expr(op.right)
        color = maybe_blue(lcolor, rcolor)
        if w_ltype != w_rtype:
            # XXX this is wrong, we need to add support for implicit conversions
            l = w_ltype.name
            r = w_rtype.name
            err = SPyTypeError(f'cannot do `{l}` {op.op} `{r}`')
            err.add('error', f'this is `{l}`', op.left.loc)
            err.add('error', f'this is `{r}`', op.right.loc)
            raise err
        return color, B.w_bool

    check_expr_Eq = check_expr_CompareOp
    check_expr_NotEq = check_expr_CompareOp
    check_expr_Lt = check_expr_CompareOp
    check_expr_LtE = check_expr_CompareOp
    check_expr_Gt = check_expr_CompareOp
    check_expr_GtE = check_expr_CompareOp

    def check_expr_GetItem(self, expr: ast.GetItem) -> tuple[Color, W_Type]:
        vcolor, w_vtype = self.check_expr(expr.value)
        icolor, w_itype = self.check_expr(expr.index)
        color = maybe_blue(vcolor, icolor)
        if w_vtype is B.w_str:
            err = self.convert_type_maybe(expr.index, w_itype, B.w_i32)
            err.add('note', f'this is a `str`', expr.value.loc)
            raise err
        else:
            got = w_vtype.name
            err = SPyTypeError(f'`{got}` does not support `[]`')
            err.add('note', f'this is a `{got}`', expr.value.loc)
            raise err

    def check_expr_HelperFunc(self, node: ast.HelperFunc
                              ) -> tuple[Color, W_Type]:
        helper = helpers.get(node.funcname)
        return 'red', helper.w_functype

    def check_expr_Call(self, call: ast.Call) -> tuple[Color, W_Type]:
        color, w_functype = self.check_expr(call.func)
        sym = self.name2sym_maybe(call.func)
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
            # TODO: kill this!
            if not self.vm.can_assign_from_to(w_arg_type, param.w_type):
                self._call_error_type_mismatch(call, sym, i,
                                               w_exp_type = param.w_type,
                                               w_got_type = w_arg_type)
        #
        color = 'red' # XXX fix me
        return color, w_functype.w_restype

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

    def _call_error_type_mismatch(self,
                                  call: ast.Call,
                                  sym: Optional[Symbol],
                                  i: int,
                                  w_exp_type: W_Type,
                                  w_got_type: W_Type
                                  ) -> NoReturn:
        err = SPyTypeError('mismatched types')
        exp = w_exp_type.name
        got = w_got_type.name
        err.add('error', f'expected `{exp}`, got `{got}`', call.args[i].loc)
        if sym:
            err.add('note', 'function defined here', sym.loc)
        raise err
