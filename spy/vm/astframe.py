from typing import TYPE_CHECKING, Any, Optional, NoReturn, Sequence
from types import NoneType
from dataclasses import dataclass
from spy import ast
from spy.location import Loc
from spy.errors import (SPyRuntimeAbort, SPyTypeError, SPyNameError,
                        SPyRuntimeError, maybe_plural)
from spy.irgen.symtable import SymTable, Symbol, Color, maybe_blue
from spy.fqn import FQN
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type, ClassBody
from spy.vm.primitive import W_Bool
from spy.vm.function import (W_Func, W_FuncType, W_ASTFunc, Namespace, CLOSURE,
                             FuncParam)
from spy.vm.func_adapter import W_FuncAdapter
from spy.vm.list import W_List, W_ListType
from spy.vm.tuple import W_Tuple
from spy.vm.modules.types import W_LiftedType
from spy.vm.modules.unsafe.struct import W_StructType
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.modules.operator import OP, OP_from_token
from spy.vm.modules.operator.convop import CONVERT_maybe
from spy.util import magic_dispatch
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


class Return(Exception):
    w_value: W_Object

    def __init__(self, w_value: W_Object) -> None:
        self.w_value = w_value


class AbstractFrame:
    """
    Frame which is able to run AST expressions/statements.

    This is an abstract class, for concrete execution see ASTFrame and
    ClassFrame.
    """
    vm: 'SPyVM'
    fqn: FQN
    closure: CLOSURE
    symtable: SymTable
    _locals: Namespace
    locals_types_w: dict[str, W_Type]

    def __init__(self, vm: 'SPyVM', fqn: FQN, symtable: SymTable,
                 closure: CLOSURE) -> None:
        assert type(self) is not AbstractFrame, 'abstract class'
        self.vm = vm
        self.fqn = fqn
        self.symtable = symtable
        self.closure = closure
        self._locals = {}
        self.locals_types_w = {}

    # overridden by DopplerFrame
    @property
    def redshifting(self) -> bool:
        return False

    @property
    def is_module_body(self) -> bool:
        return self.fqn.is_module()

    def get_unique_FQN_maybe(self, fqn: FQN) -> FQN:
        """
        Return an unique FQN to use for a type or function.

        If we are executing a module body, we can assume that the FQN is
        already unique and just return it, else we ask the VM to compute one.
        """
        if self.is_module_body:
            return fqn
        else:
            return self.vm.get_unique_FQN(fqn)

    def declare_local(self, name: str, w_type: W_Type) -> None:
        assert name not in self.locals_types_w, \
            f'variable already declared: {name}'
        if not isinstance(w_type, W_FuncType):
            self.vm.make_fqn_const(w_type)
        self.locals_types_w[name] = w_type

    def store_local(self, name: str, w_value: W_Object) -> None:
        self._locals[name] = w_value

    def load_local(self, name: str) -> W_Object:
        w_obj = self._locals.get(name)
        if w_obj is None:
            raise SPyRuntimeError('read from uninitialized local')
        return w_obj

    def exec_stmt(self, stmt: ast.Stmt) -> None:
        return magic_dispatch(self, 'exec_stmt', stmt)

    def typecheck_maybe(self, wop: W_OpArg,
                        varname: Optional[str]) -> Optional[W_Func]:
        if varname is None:
            return None # no typecheck needed
        w_exp_type = self.locals_types_w[varname]
        try:
            w_typeconv = CONVERT_maybe(self.vm, w_exp_type, wop)
        except SPyTypeError as err:
            exp = w_exp_type.fqn.human_name
            exp_loc = self.symtable.lookup(varname).type_loc
            if varname == '@return':
                because = ' because of return type'
            elif varname in ('@if', '@while'):
                because = ''
            else:
                because = ' because of type declaration'
            err.add('note', f'expected `{exp}`{because}', loc=exp_loc)
            raise
        return w_typeconv

    def eval_expr(self, expr: ast.Expr, *,
                  varname: Optional[str] = None
                  ) -> W_OpArg:
        wop = magic_dispatch(self, 'eval_expr', expr)
        w_typeconv = self.typecheck_maybe(wop, varname)

        if isinstance(self, ASTFrame) and self.w_func.redshifted:
            # this is just a sanity check. After redshifting, all type
            # conversions should be explicit. If w_typeconv is not None here,
            # it means that Doppler failed to insert the appropriate
            # conversion
            assert w_typeconv is None

        if w_typeconv is None:
            # no conversion needed, hooray
            return wop
        elif self.redshifting:
            # we are performing redshifting: the conversion will be handlded
            # by FuncDoppler
            return wop
        else:
            # apply the conversion immediately
            w_val = self.vm.fast_call(w_typeconv, [wop.w_val])
            return W_OpArg(
                self.vm,
                wop.color,
                w_typeconv.w_functype.w_restype,
                w_val,
                wop.loc,
                sym=wop.sym,
            )

    def eval_expr_type(self, expr: ast.Expr) -> W_Type:
        wop = self.eval_expr(expr)
        w_val = wop.w_val
        if isinstance(w_val, W_Type):
            self.vm.make_fqn_const(w_val)
            return w_val
        w_valtype = self.vm.dynamic_type(w_val)
        msg = f'expected `type`, got `{w_valtype.fqn.human_name}`'
        raise SPyTypeError.simple(msg, "expected `type`", expr.loc)

    # ==== statements ====

    def exec_stmt_Pass(self, stmt: ast.Pass) -> None:
        pass

    def exec_stmt_Return(self, ret: ast.Return) -> None:
        wop = self.eval_expr(ret.value, varname='@return')
        raise Return(wop.w_val)

    def exec_stmt_FuncDef(self, funcdef: ast.FuncDef) -> None:
        # sanity check: if it's the global __INIT__, it must be @blue
        if (self.is_module_body and
            funcdef.name == '__INIT__' and
            funcdef.color != 'blue'):
            err = SPyTypeError("the __INIT__ function must be @blue")
            err.add("error", "function defined here", funcdef.prototype_loc)
            raise err

        # evaluate the functype
        params = []
        for arg in funcdef.args:
            w_param_type = self.eval_expr_type(arg.type)
            param = FuncParam(
                name = arg.name,
                w_type = w_param_type,
                kind = 'simple'
            )
            params.append(param)
        w_restype = self.eval_expr_type(funcdef.return_type)
        w_functype = W_FuncType.new(params, w_restype, color=funcdef.color)
        # create the w_func
        fqn = self.fqn.join(funcdef.name)
        fqn = self.get_unique_FQN_maybe(fqn)
        # XXX we should capture only the names actually used in the inner func
        closure = self.closure + (self._locals,)
        w_func = W_ASTFunc(w_functype, fqn, funcdef, closure)
        self.declare_local(funcdef.name, w_functype)
        self.store_local(funcdef.name, w_func)
        self.vm.add_global(fqn, w_func)

    @staticmethod
    def metaclass_for_classdef(classdef: ast.ClassDef) -> type[W_Type]:
        if classdef.kind == 'struct':
            return W_StructType
        elif classdef.kind == 'typelift':
            return W_LiftedType
        else:
            assert False, 'only @struct and @typedef are supported for now'

    def exec_stmt_ClassDef(self, classdef: ast.ClassDef) -> None:
        from spy.vm.classframe import ClassFrame

        # compute the FQN of the class we are defining
        fqn = self.fqn.join(classdef.name)
        fqn = self.get_unique_FQN_maybe(fqn)

        # create a frame where to execute the class body
        # XXX we should capture only the names actually used in the inner frame
        closure = self.closure + (self._locals,)
        classframe = ClassFrame(self.vm, classdef, fqn, closure)
        body = classframe.run()

        # finalize type definition: we expect to find a forward-declared type
        # in the locals
        if self.is_module_body:
            w_type = self.load_local(classdef.name)
            assert isinstance(w_type, W_Type)
            assert w_type.fqn == fqn
            assert not w_type.is_defined()
            w_type.define_from_classbody(body)
            assert w_type.is_defined()
        else:
            # TEMP HACK for function-level definition, we don't have forward
            # declaration (yet)
            pyclass = ASTFrame.metaclass_for_classdef(classdef)
            w_type = pyclass.declare(fqn)
            w_meta_type = self.vm.dynamic_type(w_type)
            self.declare_local(classdef.name, w_meta_type)
            self.store_local(classdef.name, w_type)
            self.vm.add_global(fqn, w_type)
            # finalize definition
            w_type.define_from_classbody(body)

    def exec_stmt_VarDef(self, vardef: ast.VarDef) -> None:
        w_type = self.eval_expr_type(vardef.type)
        self.declare_local(vardef.name, w_type)

    def exec_stmt_Assign(self, assign: ast.Assign) -> None:
        self._exec_assign(assign.target, assign.value)

    def _exec_assign(self, target: ast.StrConst, expr: ast.Expr) -> None:
        varname = target.value
        sym = self.symtable.lookup(varname)
        if sym.is_local:
            self._exec_assign_local(target, expr)
        elif sym.is_global:
            self._exec_assign_global(target, expr)
        else:
            assert False, 'assignment to outer scopes not implemented yet'

    def _exec_assign_local(self, target: ast.StrConst, expr: ast.Expr) -> None:
        varname = target.value
        is_declared = varname in self.locals_types_w
        if is_declared:
            wop = self.eval_expr(expr, varname=varname)
        else:
            # first assignment, implicit declaration
            wop = self.eval_expr(expr)
            self.declare_local(varname, wop.w_static_type)

        if not self.redshifting:
            self.store_local(varname, wop.w_val)

    def _exec_assign_global(self, target: ast.StrConst, expr: ast.Expr) -> None:
        # XXX this is semi-wrong. We need to add an AST field to keep track of
        # which scope we want to assign to. For now we just assume that if
        # it's not local, it's module.
        varname = target.value
        sym = self.symtable.lookup(varname)
        if sym.color == 'blue':
            err = SPyTypeError("invalid assignment target")
            err.add('error', f'{sym.name} is const', target.loc)
            err.add('note', 'const declared here', sym.loc)
            err.add('note',
                    f'help: declare it as variable: `var {sym.name} ...`',
                    sym.loc)
            raise err
        wop = self.eval_expr(expr)
        if not self.redshifting:
            assert sym.fqn is not None
            self.vm.store_global(sym.fqn, wop.w_val)

    def exec_stmt_UnpackAssign(self, unpack: ast.UnpackAssign) -> None:
        wop_tup = self.eval_expr(unpack.value)
        if wop_tup.w_static_type is not B.w_tuple:
            t = wop_tup.w_static_type.fqn.human_name
            err = SPyTypeError(f'`{t}` does not support unpacking')
            err.add('error', f'this is `{t}`', unpack.value.loc)
            raise err

        w_tup = wop_tup.w_val
        assert isinstance(w_tup, W_Tuple)
        exp = len(unpack.targets)
        got = len(w_tup.items_w)
        if exp != got:
            raise SPyRuntimeError(
                f"Wrong number of values to unpack: expected {exp}, got {got}"
            )
        for i, target in enumerate(unpack.targets):
            # fabricate an expr to get an individual item of the tuple
            expr = ast.GetItem(
                loc = unpack.value.loc,
                value = unpack.value,
                index = ast.Constant(
                    loc = unpack.value.loc,
                    value = i
                )
            )
            self._exec_assign(target, expr)

    def exec_stmt_SetAttr(self, node: ast.SetAttr) -> None:
        wop_obj = self.eval_expr(node.target)
        wop_attr = self.eval_expr(node.attr)
        wop_value = self.eval_expr(node.value)
        w_opimpl = self.vm.call_OP(OP.w_SETATTR, [wop_obj, wop_attr, wop_value])
        self.eval_opimpl(node, w_opimpl, [wop_obj, wop_attr, wop_value])

    def exec_stmt_SetItem(self, node: ast.SetItem) -> None:
        wop_obj = self.eval_expr(node.target)
        wop_i = self.eval_expr(node.index)
        wop_v = self.eval_expr(node.value)
        w_opimpl = self.vm.call_OP(OP.w_SETITEM, [wop_obj, wop_i, wop_v])
        self.eval_opimpl(node, w_opimpl, [wop_obj, wop_i, wop_v])

    def exec_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> None:
        self.eval_expr(stmt.value)

    def exec_stmt_If(self, if_node: ast.If) -> None:
        wop_cond = self.eval_expr(if_node.test, varname='@if')
        assert isinstance(wop_cond.w_val, W_Bool)
        if self.vm.is_True(wop_cond.w_val):
            for stmt in if_node.then_body:
                self.exec_stmt(stmt)
        else:
            for stmt in if_node.else_body:
                self.exec_stmt(stmt)

    def exec_stmt_While(self, while_node: ast.While) -> None:
        while True:
            wop_cond = self.eval_expr(while_node.test, varname='@while')
            assert isinstance(wop_cond.w_val, W_Bool)
            if self.vm.is_False(wop_cond.w_val):
                break
            for stmt in while_node.body:
                self.exec_stmt(stmt)

    # ==== expressions ====

    def eval_expr_Constant(self, const: ast.Constant) -> W_OpArg:
        # unsupported literals are rejected directly by the parser, see
        # Parser.from_py_expr_Constant
        T = type(const.value)
        assert T in (int, float, bool, NoneType)
        w_val = self.vm.wrap(const.value)
        w_type = self.vm.dynamic_type(w_val)
        return W_OpArg(self.vm, 'blue', w_type, w_val, const.loc)

    def eval_expr_StrConst(self, const: ast.StrConst) -> W_OpArg:
        w_val = self.vm.wrap(const.value)
        return W_OpArg(self.vm, 'blue', B.w_str, w_val, const.loc)

    def eval_expr_FQNConst(self, const: ast.FQNConst) -> W_OpArg:
        w_value = self.vm.lookup_global(const.fqn)
        assert w_value is not None
        return W_OpArg.from_w_obj(self.vm, w_value)

    def eval_expr_Name(self, name: ast.Name) -> W_OpArg:
        varname = name.id
        sym = self.symtable.lookup_maybe(varname)
        if sym is None:
            msg = f"name `{name.id}` is not defined"
            raise SPyNameError.simple(msg, "not found in this scope", name.loc)
        if sym.fqn is not None:
            return self.eval_Name_global(name, sym)
        elif sym.is_local:
            return self.eval_Name_local(name, sym)
        else:
            return self.eval_Name_outer(name, sym)

    def eval_Name_global(self, name: ast.Name, sym: Symbol) -> W_OpArg:
        assert sym.fqn is not None
        w_val = self.vm.lookup_global(sym.fqn)
        assert w_val is not None
        w_type = self.vm.dynamic_type(w_val)
        return W_OpArg(self.vm, sym.color, w_type, w_val, name.loc, sym=sym)

    def eval_Name_local(self, name: ast.Name, sym: Symbol) -> W_OpArg:
        w_type = self.locals_types_w[name.id]
        if sym.color == 'red' and self.redshifting:
            w_val = None
        else:
            w_val = self.load_local(name.id)
        return W_OpArg(self.vm, sym.color, w_type, w_val, name.loc, sym=sym)

    def eval_Name_outer(self, name: ast.Name, sym: Symbol) -> W_OpArg:
        color: Color = 'blue'  # closed-over variables are always blue
        namespace = self.closure[sym.level]
        w_val = namespace[sym.name]
        assert w_val is not None
        w_type = self.vm.dynamic_type(w_val)
        return W_OpArg(self.vm, color, w_type, w_val, name.loc, sym=sym)

    def eval_opimpl(self, op: ast.Node, w_opimpl: W_Func,
                    args_wop: list[W_OpArg]) -> W_OpArg:
        # hack hack hack
        # result color:
        #   - pure function and blue arguments -> blue
        #   - red function -> red
        #   - blue function -> blue
        # XXX what happens if we try to call a blue func with red arguments?
        w_functype = w_opimpl.w_functype
        if w_opimpl.is_pure():
            colors = [wop.color for wop in args_wop]
            color = maybe_blue(*colors)
        else:
            color = w_functype.color

        if color == 'red' and self.redshifting:
            w_res = None
        else:
            args_w = [wop.w_val for wop in args_wop]
            w_res = self.vm.fast_call(w_opimpl, args_w)

        return W_OpArg(self.vm, color, w_functype.w_restype, w_res, op.loc)

    def eval_expr_BinOp(self, binop: ast.BinOp) -> W_OpArg:
        w_OP = OP_from_token(binop.op) # e.g., w_ADD, w_MUL, etc.
        wop_l = self.eval_expr(binop.left)
        wop_r = self.eval_expr(binop.right)
        w_opimpl = self.vm.call_OP(w_OP, [wop_l, wop_r])
        return self.eval_opimpl(
            binop,
            w_opimpl,
            [wop_l, wop_r]
        )

    eval_expr_Add = eval_expr_BinOp
    eval_expr_Sub = eval_expr_BinOp
    eval_expr_Mul = eval_expr_BinOp
    eval_expr_Div = eval_expr_BinOp
    eval_expr_Eq = eval_expr_BinOp
    eval_expr_NotEq = eval_expr_BinOp
    eval_expr_Lt = eval_expr_BinOp
    eval_expr_LtE = eval_expr_BinOp
    eval_expr_Gt = eval_expr_BinOp
    eval_expr_GtE = eval_expr_BinOp

    def eval_expr_Call(self, call: ast.Call) -> W_OpArg:
        wop_func = self.eval_expr(call.func)
        # STATIC_TYPE is special
        if wop_func.color == 'blue' and wop_func.w_val is B.w_STATIC_TYPE:
            return self._eval_STATIC_TYPE(wop_func, call)
        args_wop = [self.eval_expr(arg) for arg in call.args]
        w_opimpl = self.vm.call_OP(OP.w_CALL, [wop_func]+args_wop)
        return self.eval_opimpl(call, w_opimpl, [wop_func]+args_wop)

    def _eval_STATIC_TYPE(self, wop_func: W_OpArg, call: ast.Call) -> W_OpArg:
        for arg in call.args:
            if not isinstance(arg, (ast.Name, ast.Constant, ast.StrConst)):
                msg = 'STATIC_TYPE works only on simple expressions'
                E = arg.__class__.__name__
                raise SPyTypeError.simple(msg, f'{E} not allowed here', arg.loc)

        args_wop = [self.eval_expr(arg) for arg in call.args]
        w_opimpl = self.vm.call_OP(OP.w_CALL, [wop_func]+args_wop)
        assert len(call.args) == 1
        w_argtype = args_wop[0].w_static_type
        return W_OpArg.from_w_obj(self.vm, w_argtype)

    def eval_expr_CallMethod(self, op: ast.CallMethod) -> W_Object:
        wop_obj = self.eval_expr(op.target)
        wop_meth = self.eval_expr(op.method)
        args_wop = [self.eval_expr(arg) for arg in op.args]
        w_opimpl = self.vm.call_OP(
            OP.w_CALL_METHOD,
            [wop_obj, wop_meth] + args_wop
        )
        return self.eval_opimpl(
            op,
            w_opimpl,
            [wop_obj, wop_meth] + args_wop,
        )

    def eval_expr_GetItem(self, op: ast.GetItem) -> W_OpArg:
        wop_obj = self.eval_expr(op.value)
        wop_i = self.eval_expr(op.index)
        w_opimpl = self.vm.call_OP(OP.w_GETITEM, [wop_obj, wop_i])
        return self.eval_opimpl(op, w_opimpl, [wop_obj, wop_i])

    def eval_expr_GetAttr(self, op: ast.GetAttr) -> W_OpArg:
        wop_obj = self.eval_expr(op.value)
        wop_attr = self.eval_expr(op.attr)
        w_opimpl = self.vm.call_OP(OP.w_GETATTR, [wop_obj, wop_attr])
        return self.eval_opimpl(op, w_opimpl, [wop_obj, wop_attr])

    def eval_expr_List(self, op: ast.List) -> W_Object:
        items_wop = []
        w_itemtype = None
        color: Color = 'red' # XXX should be blue?
        for item in op.items:
            wop_item = self.eval_expr(item)
            items_wop.append(wop_item)
            color = maybe_blue(color, wop_item.color)
            if w_itemtype is None:
                w_itemtype = wop_item.w_static_type
            w_itemtype = self.vm.union_type(w_itemtype, wop_item.w_static_type)
        #
        # XXX we need to handle empty lists
        assert w_itemtype is not None
        w_listtype = self.vm.make_list_type(w_itemtype)
        if color == 'red' and self.redshifting:
            w_val = None
        else:
            items_w = [wop.w_val for wop in items_wop]
            w_val = W_List(w_listtype, items_w)
        return W_OpArg(self.vm, color, w_listtype, w_val, op.loc)

    def eval_expr_Tuple(self, op: ast.Tuple) -> W_OpArg:
        items_wop = [self.eval_expr(item) for item in op.items]
        colors = [wop.color for wop in items_wop]
        color = maybe_blue(*colors)
        if color == 'red' and self.redshifting:
            w_val = None
        else:
            items_w = [wop.w_val for wop in items_wop]
            w_val = W_Tuple(items_w)
        return W_OpArg(self.vm, color, B.w_tuple, w_val, op.loc)



class ASTFrame(AbstractFrame):
    """
    A frame to execute and ASTFunc
    """
    w_func: W_ASTFunc
    funcdef: ast.FuncDef

    def __init__(self, vm: 'SPyVM', w_func: W_ASTFunc) -> None:
        assert isinstance(w_func, W_ASTFunc)
        super().__init__(vm, w_func.fqn, w_func.funcdef.symtable,
                         w_func.closure)
        self.w_func = w_func
        self.funcdef = w_func.funcdef

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        if self.w_func.redshifted:
            extra = ' (redshifted)'
        elif self.w_func.color == 'blue':
            extra = ' (blue)'
        else:
            extra = ''
        return f'<{cls} for {self.w_func.fqn}{extra}>'

    def run(self, args_w: Sequence[W_Object]) -> W_Object:
        self.declare_arguments()
        self.init_arguments(args_w)
        try:
            for stmt in self.funcdef.body:
                self.exec_stmt(stmt)
            #
            # we reached the end of the function. If it's void, we can return
            # None, else it's an error.
            if self.w_func.w_functype.w_restype in (B.w_void, B.w_dynamic):
                return B.w_None
            else:
                loc = self.w_func.funcdef.loc.make_end_loc()
                msg = 'reached the end of the function without a `return`'
                raise SPyTypeError.simple(msg, 'no return', loc)

        except Return as e:
            return e.w_value

    def declare_arguments(self) -> None:
        w_functype = self.w_func.w_functype
        self.declare_local('@if', B.w_bool)
        self.declare_local('@while', B.w_bool)
        self.declare_local('@return', w_functype.w_restype)
        for param in w_functype.params:
            self.declare_local(param.name, param.w_type)

    def init_arguments(self, args_w: Sequence[W_Object]) -> None:
        """
        Store the arguments in args_w in the appropriate local var
        """
        w_functype = self.w_func.w_functype
        params = self.w_func.w_functype.params
        for param, w_arg in zip(params, args_w, strict=True):
            assert self.vm.isinstance(w_arg, param.w_type)
            self.store_local(param.name, w_arg)
