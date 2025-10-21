from types import NoneType
from typing import TYPE_CHECKING, Optional, Sequence

from spy import ast
from spy.analyze.symtable import Color, Symbol, SymTable, maybe_blue
from spy.errors import WIP, SPyError
from spy.fqn import FQN
from spy.location import Loc
from spy.util import magic_dispatch
from spy.vm.b import B
from spy.vm.cell import W_Cell
from spy.vm.exc import W_TypeError
from spy.vm.function import CLOSURE, FuncParam, LocalVar, W_ASTFunc, W_Func, W_FuncType
from spy.vm.list import W_List
from spy.vm.modules.operator import OP, OP_from_token, OP_unary_from_token
from spy.vm.modules.operator.convop import CONVERT_maybe
from spy.vm.modules.types import TYPES, W_LiftedType
from spy.vm.object import W_Object, W_Type
from spy.vm.opimpl import W_OpImpl
from spy.vm.opspec import W_MetaArg
from spy.vm.primitive import W_Bool
from spy.vm.struct import W_StructType
from spy.vm.tuple import W_Tuple
from spy.vm.typechecker import maybe_plural

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


class Return(Exception):
    "Raised to implement the 'return' statement"

    w_value: W_Object

    def __init__(self, w_value: W_Object) -> None:
        self.w_value = w_value


class Break(Exception):
    "Raised to implement the 'break' statement"


class Continue(Exception):
    "Raised to implement the 'continue' statement"


class AbstractFrame:
    """
    Frame which is able to run AST expressions/statements.

    This is an abstract class, for concrete execution see ASTFrame and
    ClassFrame.
    """

    vm: "SPyVM"
    ns: FQN
    closure: CLOSURE
    symtable: SymTable
    locals: dict[str, LocalVar]
    specialized_names: dict[ast.Name, ast.Expr]
    specialized_assigns: dict[ast.Assign, ast.Stmt]
    desugared_fors: dict[ast.For, tuple[ast.Assign, ast.While]]

    def __init__(
        self, vm: "SPyVM", ns: FQN, symtable: SymTable, closure: CLOSURE
    ) -> None:
        assert type(self) is not AbstractFrame, "abstract class"
        self.vm = vm
        self.ns = ns
        self.symtable = symtable
        self.closure = closure
        self.locals = {}

        # ast.Name and ast.Assign are special, because depending on the
        # content of the symtable it has different meanings (e.g. local, outer
        # direct, outer cell, ...), so we need some logic to distinguish
        # between the cases.
        #
        # The first time eval_expr_Name and exec_stmt_Assign are called, they
        # understand which kind of name it is and create specialized ast.Name*
        # or ast.Assign* nodes, which are then used from now on.  This is also
        # useful for Doppler, since shifting simply means to return the
        # specialized version.
        self.specialized_names = {}
        self.specialized_assigns = {}
        self.desugared_fors = {}

    # overridden by DopplerFrame
    @property
    def redshifting(self) -> bool:
        return False

    def get_locals_types_w(self) -> dict[str, W_Type]:
        return {
            name: lv.w_T
            for name, lv in self.locals.items()
        }  # fmt: skip

    def declare_local(self, name: str, w_type: W_Type, loc: Loc) -> None:
        if name in self.locals:
            # this is the same check that we already do in
            # ScopeAnalyzer.define_name. This logic is duplicated because for
            # RED frames we raise the error eagerly in the analyzer, but for
            # BLUE frames we raise it here
            old_loc = self.locals[name].decl_loc
            msg = f"variable `{name}` already declared"
            err = SPyError("W_ScopeError", msg)
            err.add("error", "this is the new declaration", loc)
            err.add("note", "this is the previous declaration", old_loc)
            raise err

        if not isinstance(w_type, W_FuncType):
            self.vm.make_fqn_const(w_type)
        self.locals[name] = LocalVar(varname=name, decl_loc=loc, w_T=w_type, w_val=None)

    def store_local(self, name: str, w_value: W_Object) -> None:
        self.locals[name].w_val = w_value

    def load_local(self, name: str) -> W_Object:
        localvar = self.locals.get(name)
        if localvar is None or localvar.w_val is None:
            raise SPyError("W_Exception", "read from uninitialized local")
        return localvar.w_val

    def exec_stmt(self, stmt: ast.Stmt) -> None:
        try:
            return magic_dispatch(self, "exec_stmt", stmt)
        except SPyError as exc:
            exc.add_location_maybe(stmt.loc)
            raise

    def typecheck_maybe(
        self, wam: W_MetaArg, varname: Optional[str]
    ) -> Optional[W_Func]:
        if varname is None:
            return None  # no typecheck needed
        w_exp_T = self.locals[varname].w_T
        try:
            w_typeconv = CONVERT_maybe(self.vm, w_exp_T, wam)
        except SPyError as err:
            if not err.match(W_TypeError):
                raise
            exp = w_exp_T.fqn.human_name
            exp_loc = self.symtable.lookup(varname).type_loc
            if varname == "@return":
                because = " because of return type"
            elif varname in ("@if", "@while", "@assert"):
                because = ""
            else:
                because = " because of type declaration"
            err.add("note", f"expected `{exp}`{because}", loc=exp_loc)
            raise
        return w_typeconv

    def eval_expr(self, expr: ast.Expr, *, varname: Optional[str] = None) -> W_MetaArg:
        try:
            wam = magic_dispatch(self, "eval_expr", expr)
        except SPyError as exc:
            exc.add_location_maybe(expr.loc)
            raise

        w_typeconv = self.typecheck_maybe(wam, varname)

        if isinstance(self, ASTFrame) and self.w_func.redshifted:
            # this is just a sanity check. After redshifting, all type
            # conversions should be explicit. If w_typeconv is not None here,
            # it means that Doppler failed to insert the appropriate
            # conversion
            assert w_typeconv is None

        if w_typeconv is None:
            # no conversion needed, hooray
            return wam
        elif self.redshifting:
            # we are performing redshifting: the conversion will be handlded
            # by FuncDoppler
            return wam
        else:
            # apply the conversion immediately
            w_val = self.vm.fast_call(w_typeconv, [wam.w_val])
            return W_MetaArg(
                self.vm,
                wam.color,
                w_typeconv.w_functype.w_restype,
                w_val,
                wam.loc,
                sym=wam.sym,
            )

    def eval_expr_type(self, expr: ast.Expr) -> W_Type:
        wam = self.eval_expr(expr)
        w_val = wam.w_val
        if isinstance(w_val, W_Type):
            self.vm.make_fqn_const(w_val)
            return w_val
        elif w_val is B.w_None:
            # special case None and allow to use it as a type even if it's not
            return TYPES.w_NoneType
        w_valtype = self.vm.dynamic_type(w_val)
        msg = f"expected `type`, got `{w_valtype.fqn.human_name}`"
        raise SPyError.simple("W_TypeError", msg, "expected `type`", expr.loc)

    # ==== statements ====

    def exec_stmt_Pass(self, stmt: ast.Pass) -> None:
        pass

    def exec_stmt_Return(self, ret: ast.Return) -> None:
        wam = self.eval_expr(ret.value, varname="@return")
        raise Return(wam.w_val)

    def exec_stmt_Break(self, brk: ast.Break) -> None:
        raise Break()

    def exec_stmt_Continue(self, cont: ast.Continue) -> None:
        raise Continue()

    def exec_stmt_FuncDef(self, funcdef: ast.FuncDef) -> None:
        # evaluate the functype
        params = []
        for arg in funcdef.args:
            w_param_type = self.eval_expr_type(arg.type)
            param = FuncParam(w_T=w_param_type, kind="simple")
            params.append(param)

        if funcdef.vararg:
            w_param_type = self.eval_expr_type(funcdef.vararg.type)
            param = FuncParam(w_T=w_param_type, kind="var_positional")
            params.append(param)

        w_restype = self.eval_expr_type(funcdef.return_type)
        w_functype = W_FuncType.new(
            params, w_restype, color=funcdef.color, kind=funcdef.kind
        )
        # create the w_func
        fqn = self.ns.join(funcdef.name)
        fqn = self.vm.get_unique_FQN(fqn)
        # XXX we should capture only the names actually used in the inner func
        closure = self.closure + (self.locals,)

        # this is just a cosmetic nicety. In presence of decorators, "mod.foo"
        # will NOT necessarily contain the function object which is being
        # created. If we call the function FQN("mod::foo"), it might create
        # confusion. The solution is that in presence of decorators, we use
        # FQN("mod::foo#__bare__") as the name of the function, to make it
        # clear is the undecorated version.
        if funcdef.decorators:
            fqn = fqn.with_suffix("__bare__")

        w_func: W_Object = W_ASTFunc(w_functype, fqn, funcdef, closure)
        self.vm.add_global(fqn, w_func)

        if funcdef.decorators:
            for deco in reversed(funcdef.decorators):
                # create a tmp Call node to evaluate
                call_node = ast.Call(
                    loc=deco.loc,
                    func=deco,
                    args=[ast.FQNConst(funcdef.loc, self.vm.make_fqn_const(w_func))],
                )
                wam_inner = self.eval_expr_Call(call_node)
                assert wam_inner.color == "blue"
                w_func = wam_inner.w_blueval

        w_T = self.vm.dynamic_type(w_func)
        self.declare_local(funcdef.name, w_T, funcdef.prototype_loc)
        self.store_local(funcdef.name, w_func)

    @staticmethod
    def metaclass_for_classdef(classdef: ast.ClassDef) -> type[W_Type]:
        if classdef.kind == "struct":
            return W_StructType
        elif classdef.kind == "typelift":
            return W_LiftedType
        else:
            assert False, "only @struct and @typedef are supported for now"

    def fwdecl_ClassDef(self, classdef: ast.ClassDef) -> None:
        """
        Create a forward-declaration for the given classdef
        """
        fqn = self.ns.join(classdef.name)
        fqn = self.vm.get_unique_FQN(fqn)
        pyclass = self.metaclass_for_classdef(classdef)
        w_typedecl = pyclass.declare(fqn)
        w_meta_type = self.vm.dynamic_type(w_typedecl)
        self.declare_local(classdef.name, w_meta_type, classdef.loc)
        self.store_local(classdef.name, w_typedecl)
        self.vm.add_global(fqn, w_typedecl)

    def exec_stmt_ClassDef(self, classdef: ast.ClassDef) -> None:
        from spy.vm.classframe import ClassFrame

        # we are DEFINING a type which has already been declared by
        # fwdecl_ClassDef. Look it up
        w_T = self.load_local(classdef.name)
        assert isinstance(w_T, W_Type)
        assert w_T.fqn.parts[-1].name == classdef.name  # sanity check
        assert not w_T.is_defined()

        # create a frame where to execute the class body
        # XXX we should capture only the names actually used in the inner frame
        closure = self.closure + (self.locals,)
        classframe = ClassFrame(self.vm, classdef, w_T.fqn, closure)
        body = classframe.run()

        # finalize type definition
        w_T.define_from_classbody(self.vm, body)
        assert w_T.is_defined()

    def exec_stmt_VarDef(self, vardef: ast.VarDef) -> None:
        # Possible cases:
        #   declaration    (not is_auto and not value):  [var] x: i32
        #   definition     (not is_auto and value):      [var] x: i32 = 0
        #   type inference (is_auto and value):          var   x      = 0
        #   invalid        (is_auto and not value):      var   x
        #
        # Note that the "type inference" case is basically a simple Assign.
        varname = vardef.name.value
        sym = self.symtable.lookup(varname)
        is_auto = isinstance(vardef.type, ast.Auto)

        if vardef.value is None:
            # declaration
            assert not is_auto, "invalid VarDef"
            w_T = self.eval_expr_type(vardef.type)
            self.declare_local(varname, w_T, vardef.loc)
            return

        if is_auto:
            # type inference
            wam = self.eval_expr(vardef.value)
            w_T = wam.w_static_T
            self.declare_local(varname, w_T, vardef.loc)
        else:
            # definition
            w_T = self.eval_expr_type(vardef.type)
            self.declare_local(varname, w_T, vardef.loc)
            wam = self.eval_expr(vardef.value, varname=varname)

        # store the value (common for "type inference" and "definition")
        if not self.redshifting or sym.color == "blue":
            self.store_local(varname, wam.w_val)

    def exec_stmt_Assign(self, assign: ast.Assign) -> None:
        # see the commnet in __init__ about specialized_assigns
        specialized = self.specialized_assigns.get(assign)
        if specialized is None:
            specialized = self._specialize_Assign(assign)
            self.specialized_assigns[assign] = specialized
        self.exec_stmt(specialized)

    def _specialize_Assign(self, assign: ast.Assign) -> ast.Stmt:
        target = assign.target
        varname = target.value
        sym = self.symtable.lookup(varname)

        if sym.varkind == "const":
            err = SPyError("W_TypeError", "invalid assignment target")
            err.add("error", f"{sym.name} is const", target.loc)
            err.add("note", f"const declared here ({sym.varkind_origin})", sym.loc)

            if sym.varkind_origin == "global-const":
                err.add(
                    "note",
                    f"help: declare it as variable: `var {sym.name} ...`",
                    sym.loc,
                )
            ## elif sym.varkind_origin == "blue-param":
            ##     err.add(
            ##         "note",
            ##         "blue function arguments are const by default",
            ##         sym.loc,
            ##     )

            raise err

        elif sym.storage == "direct":
            assert sym.is_local
            return ast.AssignLocal(assign.loc, target, assign.value)

        elif sym.storage == "cell":
            outervars = self.closure[-sym.level]
            w_cell = outervars[sym.name].w_val
            assert isinstance(w_cell, W_Cell)
            return ast.AssignCell(
                loc=assign.loc,
                target=assign.target,
                target_fqn=w_cell.fqn,
                value=assign.value,
            )

        else:
            assert False

    def exec_stmt_AssignLocal(self, assign: ast.AssignLocal) -> None:
        target = assign.target
        varname = target.value
        is_declared = varname in self.locals
        if is_declared:
            wam = self.eval_expr(assign.value, varname=varname)
        else:
            # first assignment, implicit declaration
            wam = self.eval_expr(assign.value)
            self.declare_local(varname, wam.w_static_T, target.loc)

        if not self.redshifting:
            self.store_local(varname, wam.w_val)

    def exec_stmt_AssignCell(self, assign: ast.AssignCell) -> None:
        target = assign.target
        varname = target.value
        wam = self.eval_expr(assign.value)
        if not self.redshifting:
            w_cell = self.vm.lookup_global(assign.target_fqn)
            assert isinstance(w_cell, W_Cell)
            w_cell.set(wam.w_val)

    def exec_stmt_UnpackAssign(self, unpack: ast.UnpackAssign) -> None:
        wam_tup = self.eval_expr(unpack.value)
        if wam_tup.w_static_T is not B.w_tuple:
            t = wam_tup.w_static_T.fqn.human_name
            err = SPyError(
                "W_TypeError",
                f"`{t}` does not support unpacking",
            )
            err.add("error", f"this is `{t}`", unpack.value.loc)
            raise err

        if wam_tup.color == "red":
            raise SPyError.simple(
                "W_WIP",
                "redshift of UnpackAssign works only for blue tuples",
                "this is red",
                unpack.value.loc,
            )

        w_tup = wam_tup.w_val
        assert isinstance(w_tup, W_Tuple)
        exp = len(unpack.targets)
        got = len(w_tup.items_w)
        if exp != got:
            # we cannot use ValueError because we want an exception type which
            # inherits from StaticError.
            targets_loc = Loc.combine(
                start=unpack.targets[0].loc,
                end=unpack.targets[-1].loc,
            )
            err = SPyError(
                "W_TypeError",
                f"Wrong number of values to unpack",
            )
            exp_values = maybe_plural(exp, "value")
            got_values = maybe_plural(got, "value")
            err.add("error", f"expected {exp} {exp_values}", targets_loc)
            err.add("error", f"got {got} {got_values}", unpack.value.loc)
            raise err

        for i, target in enumerate(unpack.targets):
            # fabricate an expr to get an individual item of the tuple
            expr = ast.GetItem(
                loc=unpack.value.loc,
                value=unpack.value,
                args=[ast.Constant(loc=unpack.value.loc, value=i)],
            )
            # fabricate an ast.Assign
            # XXX: ideally we should cache the specialization instead of
            # rebuilding it at every exec
            assign = self._specialize_Assign(
                ast.Assign(loc=unpack.loc, target=target, value=expr)
            )
            self.exec_stmt(assign)

    def exec_stmt_AugAssign(self, node: ast.AugAssign) -> None:
        # XXX: eventually we want to support things like __IADD__ etc, but for
        # now we just delegate to _ADD__.
        assign = self._desugar_AugAssign(node)
        self.exec_stmt(assign)

    def _desugar_AugAssign(self, node: ast.AugAssign) -> ast.Assign:
        # transform "x += 1" into "x = x + 1"
        return ast.Assign(
            loc=node.loc,
            target=node.target,
            value=ast.BinOp(
                loc=node.loc,
                op=node.op,
                left=ast.Name(loc=node.target.loc, id=node.target.value),
                right=node.value,
            ),
        )

    def exec_stmt_SetAttr(self, node: ast.SetAttr) -> None:
        wam_obj = self.eval_expr(node.target)
        wam_name = self.eval_expr(node.attr)
        wam_value = self.eval_expr(node.value)
        w_opimpl = self.vm.call_OP(
            node.loc, OP.w_SETATTR, [wam_obj, wam_name, wam_value]
        )
        self.eval_opimpl(node, w_opimpl, [wam_obj, wam_name, wam_value])

    def exec_stmt_SetItem(self, node: ast.SetItem) -> None:
        wam_obj = self.eval_expr(node.target)
        args_wam = [self.eval_expr(arg) for arg in node.args]
        wam_v = self.eval_expr(node.value)
        wams = [wam_obj] + args_wam + [wam_v]
        w_opimpl = self.vm.call_OP(
            node.loc,
            OP.w_SETITEM,
            wams,
        )
        self.eval_opimpl(node, w_opimpl, wams)

    def exec_stmt_StmtExpr(self, stmt: ast.StmtExpr) -> None:
        self.eval_expr(stmt.value)

    def exec_stmt_If(self, if_node: ast.If) -> None:
        wam_cond = self.eval_expr(if_node.test, varname="@if")
        assert isinstance(wam_cond.w_val, W_Bool)
        if self.vm.is_True(wam_cond.w_val):
            for stmt in if_node.then_body:
                self.exec_stmt(stmt)
        else:
            for stmt in if_node.else_body:
                self.exec_stmt(stmt)

    def exec_stmt_While(self, while_node: ast.While) -> None:
        while True:
            wam_cond = self.eval_expr(while_node.test, varname="@while")
            assert isinstance(wam_cond.w_val, W_Bool)
            if self.vm.is_False(wam_cond.w_val):
                break
            try:
                for stmt in while_node.body:
                    self.exec_stmt(stmt)
            except Break:
                break
            except Continue:
                continue

    def exec_stmt_For(self, for_node: ast.For) -> None:
        # see the comment in __init__ about desugared_fors
        if for_node in self.desugared_fors:
            init_iter, while_loop = self.desugared_fors[for_node]
        else:
            init_iter, while_loop = self._desugar_For(for_node)
            self.desugared_fors[for_node] = (init_iter, while_loop)
        self.exec_stmt(init_iter)
        self.exec_stmt(while_loop)

    def _desugar_For(self, for_node: ast.For) -> tuple[ast.Assign, ast.While]:
        # Desugar the for loop into an equivalent while loop
        # Transform:
        #     for i in X:
        #         body
        # Into:
        #     it = X.__fastiter__()
        #     while it.__continue_iteration__():
        #         i = it.__item__()
        #         it = it.__next__()
        #         body
        #
        # (instead of 'it' we use the special variable '_$iterN')
        #
        # Note that "body" is placed AFTER the call to it.__next__(). This
        # way, 'continue' works out of the box.
        iter_name = f"_$iter{for_node.seq}"
        iter_sym = self.symtable.lookup(iter_name)
        iter_target = ast.StrConst(for_node.loc, iter_name)

        # it = X.__fastiter__()
        init_iter = ast.Assign(
            loc=for_node.loc,
            target=iter_target,
            value=ast.CallMethod(
                loc=for_node.loc,
                target=for_node.iter,
                method=ast.StrConst(for_node.loc, "__fastiter__"),
                args=[],
            ),
        )
        # i = it.__item__()
        assign_item = ast.Assign(
            loc=for_node.loc,
            target=for_node.target,
            value=ast.CallMethod(
                loc=for_node.loc,
                target=ast.NameLocal(for_node.loc, iter_sym),
                method=ast.StrConst(for_node.loc, "__item__"),
                args=[],
            ),
        )
        # it = it.__next__()
        advance_iter = ast.Assign(
            loc=for_node.loc,
            target=iter_target,
            value=ast.CallMethod(
                loc=for_node.loc,
                target=ast.NameLocal(for_node.loc, iter_sym),
                method=ast.StrConst(for_node.loc, "__next__"),
                args=[],
            ),
        )
        # while it.__continue_iteration__(): ...
        while_loop = ast.While(
            loc=for_node.loc,
            test=ast.CallMethod(
                loc=for_node.loc,
                target=ast.NameLocal(for_node.loc, iter_sym),
                method=ast.StrConst(for_node.loc, "__continue_iteration__"),
                args=[],
            ),
            body=[assign_item, advance_iter] + for_node.body,
        )
        return init_iter, while_loop

    def exec_stmt_Raise(self, raise_node: ast.Raise) -> None:
        wam_exc = self.eval_expr(raise_node.exc)
        w_opimpl = self.vm.call_OP(raise_node.loc, OP.w_RAISE, [wam_exc])
        self.eval_opimpl(raise_node, w_opimpl, [wam_exc])

    def exec_stmt_Assert(self, assert_node: ast.Assert) -> None:
        wam_assert = self.eval_expr(assert_node.test, varname="@assert")
        assert isinstance(wam_assert.w_val, W_Bool)

        if self.vm.is_False(wam_assert.w_val):
            plain_msg = "assertion failed"

            if assert_node.msg is not None:
                wam_msg = self.eval_expr(assert_node.msg)
                if wam_msg.w_static_T is B.w_str:
                    plain_msg = self.vm.unwrap_str(wam_msg.w_val)
                else:
                    err = SPyError("W_TypeError", "mismatched types")
                    err.add(
                        "error",
                        f"expected `str`, got `{wam_msg.w_static_T.fqn.human_name}`",
                        loc=wam_msg.loc,
                    )
                    raise err

            raise SPyError.simple(
                etype="W_AssertionError",
                primary=plain_msg,
                secondary="assertion failed",
                loc=assert_node.loc,
            )

    # ==== expressions ====

    def eval_expr_Constant(self, const: ast.Constant) -> W_MetaArg:
        # unsupported literals are rejected directly by the parser, see
        # Parser.from_py_expr_Constant
        T = type(const.value)
        assert T in (int, float, bool, NoneType)
        w_val = self.vm.wrap(const.value)
        w_T = self.vm.dynamic_type(w_val)
        return W_MetaArg(self.vm, "blue", w_T, w_val, const.loc)

    def eval_expr_StrConst(self, const: ast.StrConst) -> W_MetaArg:
        w_val = self.vm.wrap(const.value)
        return W_MetaArg(self.vm, "blue", B.w_str, w_val, const.loc)

    def eval_expr_LocConst(self, const: ast.LocConst) -> W_MetaArg:
        w_val = self.vm.wrap(const.value)
        return W_MetaArg(self.vm, "blue", TYPES.w_Loc, w_val, const.loc)

    def eval_expr_FQNConst(self, const: ast.FQNConst) -> W_MetaArg:
        w_value = self.vm.lookup_global(const.fqn)
        assert w_value is not None
        return W_MetaArg.from_w_obj(self.vm, w_value)

    def eval_expr_Name(self, name: ast.Name) -> W_MetaArg:
        # see the comment in __init__ about specialized_names
        specialized = self.specialized_names.get(name)
        if specialized is None:
            specialized = self._specialize_Name(name)
            self.specialized_names[name] = specialized
        return self.eval_expr(specialized)

    def _specialize_Name(self, name: ast.Name) -> ast.Expr:
        varname = name.id
        sym = self.symtable.lookup_maybe(varname)
        assert sym is not None
        if sym.is_local:
            assert sym.storage == "direct"
            return ast.NameLocal(name.loc, sym)
        elif sym.storage == "direct":
            return ast.NameOuterDirect(name.loc, sym)
        elif sym.storage == "cell":
            outervars = self.closure[-sym.level]
            w_cell = outervars[sym.name].w_val
            assert isinstance(w_cell, W_Cell)
            return ast.NameOuterCell(name.loc, sym, w_cell.fqn)
        elif sym.storage == "NameError":
            msg = f"name `{name.id}` is not defined"
            raise SPyError.simple(
                "W_NameError",
                msg,
                "not found in this scope",
                name.loc,
            )
        else:
            assert False

    def eval_expr_NameLocal(self, name: ast.NameLocal) -> W_MetaArg:
        sym = name.sym
        w_T = self.locals[sym.name].w_T
        if sym.color == "red" and self.redshifting:
            w_val = None
        else:
            w_val = self.load_local(sym.name)
        return W_MetaArg(self.vm, sym.color, w_T, w_val, name.loc, sym=sym)

    def eval_expr_NameOuterDirect(self, name: ast.NameOuterDirect) -> W_MetaArg:
        color: Color = "blue"  # closed-over variables are always blue
        sym = name.sym
        assert not sym.is_local
        outervars = self.closure[-sym.level]
        w_val = outervars[sym.name].w_val
        assert w_val is not None
        w_T = self.vm.dynamic_type(w_val)
        return W_MetaArg(self.vm, color, w_T, w_val, name.loc, sym=sym)

    def eval_expr_NameOuterCell(self, name: ast.NameOuterCell) -> W_MetaArg:
        sym = name.sym
        assert not sym.is_local
        w_cell = self.vm.lookup_global(name.fqn)
        assert isinstance(w_cell, W_Cell)
        w_val = w_cell.get()
        w_T = self.vm.dynamic_type(w_val)
        return W_MetaArg(self.vm, sym.color, w_T, w_val, name.loc, sym=sym)

    def eval_opimpl(
        self, op: ast.Node, w_opimpl: W_OpImpl, args_wam: list[W_MetaArg]
    ) -> W_MetaArg:
        # hack hack hack
        # result color:
        #   - pure function and blue arguments -> blue
        #   - red function -> red
        #   - blue function -> blue
        # XXX what happens if we try to call a blue func with red arguments?
        w_functype = w_opimpl.w_functype
        if w_opimpl.is_pure():
            colors = [wam.color for wam in args_wam]
            color = maybe_blue(*colors)
        else:
            color = w_functype.color

        if color == "red" and self.redshifting:
            w_res = None
        else:
            args_w = [wam.w_val for wam in args_wam]
            w_res = w_opimpl.execute(self.vm, args_w)

        return W_MetaArg(self.vm, color, w_functype.w_restype, w_res, op.loc)

    def eval_expr_BinOp(self, binop: ast.BinOp) -> W_MetaArg:
        w_OP = OP_from_token(binop.op)  # e.g., w_ADD, w_MUL, etc.
        wam_l = self.eval_expr(binop.left)
        wam_r = self.eval_expr(binop.right)
        w_opimpl = self.vm.call_OP(binop.loc, w_OP, [wam_l, wam_r])
        return self.eval_opimpl(binop, w_opimpl, [wam_l, wam_r])

    def eval_expr_CmpOp(self, op: ast.CmpOp) -> W_MetaArg:
        w_OP = OP_from_token(op.op)  # e.g., w_ADD, w_MUL, etc.
        wam_l = self.eval_expr(op.left)
        wam_r = self.eval_expr(op.right)
        w_opimpl = self.vm.call_OP(op.loc, w_OP, [wam_l, wam_r])
        return self.eval_opimpl(op, w_opimpl, [wam_l, wam_r])

    def eval_expr_UnaryOp(self, unop: ast.UnaryOp) -> W_MetaArg:
        w_OP = OP_unary_from_token(unop.op)
        wam_v = self.eval_expr(unop.value)
        w_opimpl = self.vm.call_OP(unop.loc, w_OP, [wam_v])
        return self.eval_opimpl(unop, w_opimpl, [wam_v])

    def eval_expr_Call(self, call: ast.Call) -> W_MetaArg:
        wam_func = self.eval_expr(call.func)
        args_wam = [self.eval_expr(arg) for arg in call.args]
        w_opimpl = self.vm.call_OP(call.loc, OP.w_CALL, [wam_func] + args_wam)
        return self.eval_opimpl(call, w_opimpl, [wam_func] + args_wam)

    def eval_expr_CallMethod(self, op: ast.CallMethod) -> W_Object:
        wam_obj = self.eval_expr(op.target)
        wam_meth = self.eval_expr(op.method)
        args_wam = [self.eval_expr(arg) for arg in op.args]
        w_opimpl = self.vm.call_OP(
            op.loc, OP.w_CALL_METHOD, [wam_obj, wam_meth] + args_wam
        )
        return self.eval_opimpl(
            op,
            w_opimpl,
            [wam_obj, wam_meth] + args_wam,
        )

    def eval_expr_GetItem(self, op: ast.GetItem) -> W_MetaArg:
        wam_obj = self.eval_expr(op.value)
        args_wam = [self.eval_expr(arg) for arg in op.args]
        w_opimpl = self.vm.call_OP(op.loc, OP.w_GETITEM, [wam_obj] + args_wam)
        return self.eval_opimpl(op, w_opimpl, [wam_obj] + args_wam)

    def eval_expr_GetAttr(self, op: ast.GetAttr) -> W_MetaArg:
        wam_obj = self.eval_expr(op.value)
        wam_name = self.eval_expr(op.attr)
        w_opimpl = self.vm.call_OP(op.loc, OP.w_GETATTR, [wam_obj, wam_name])
        return self.eval_opimpl(op, w_opimpl, [wam_obj, wam_name])

    def eval_expr_List(self, op: ast.List) -> W_Object:
        items_wam = []
        w_itemtype = None
        color: Color = "red"  # XXX should be blue?
        for item in op.items:
            wam_item = self.eval_expr(item)
            items_wam.append(wam_item)
            color = maybe_blue(color, wam_item.color)
            if w_itemtype is None:
                w_itemtype = wam_item.w_static_T
            w_itemtype = self.vm.union_type(w_itemtype, wam_item.w_static_T)
        #
        # XXX we need to handle empty lists
        assert w_itemtype is not None
        w_listtype = self.vm.make_list_type(w_itemtype)
        if color == "red" and self.redshifting:
            w_val = None
        else:
            items_w = [wam.w_val for wam in items_wam]
            w_val = W_List(w_listtype, items_w)
        return W_MetaArg(self.vm, color, w_listtype, w_val, op.loc)

    def eval_expr_Tuple(self, op: ast.Tuple) -> W_MetaArg:
        items_wam = [self.eval_expr(item) for item in op.items]
        colors = [wam.color for wam in items_wam]
        color = maybe_blue(*colors)
        if color == "red" and self.redshifting:
            w_val = None
        else:
            items_w = [wam.w_val for wam in items_wam]
            w_val = W_Tuple(items_w)
        return W_MetaArg(self.vm, color, B.w_tuple, w_val, op.loc)


class ASTFrame(AbstractFrame):
    """
    A frame to execute and ASTFunc
    """

    w_func: W_ASTFunc
    funcdef: ast.FuncDef

    def __init__(
        self, vm: "SPyVM", w_func: W_ASTFunc, args_w: Optional[Sequence[W_Object]]
    ) -> None:
        # if w_func was redshifted, automatically use the new version
        if w_func.w_redshifted_into:
            w_func = w_func.w_redshifted_into
        assert isinstance(w_func, W_ASTFunc)
        ns = self.compute_ns(w_func, args_w)
        super().__init__(vm, ns, w_func.funcdef.symtable, w_func.closure)
        self.w_func = w_func
        self.funcdef = w_func.funcdef

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        if self.w_func.redshifted:
            extra = " (redshifted)"
        elif self.w_func.color == "blue":
            extra = " (blue)"
        else:
            extra = ""
        return f"<{cls} for `{self.w_func.fqn}`{extra}>"

    def compute_ns(
        self, w_func: W_ASTFunc, args_w: Optional[Sequence[W_Object]]
    ) -> FQN:
        """
        Try to generate a meaningful namespace for blue functions. The
        idea is that if we blue func takes type parameters, we want to include
        them in the qualifiers. E.g.:

            @blue
            def add(T):
                def impl(x: T, y: T) -> T:
                    return x + y
                return impl

            add(i32) # ==> add[i32]::impl
            add(str) # ==> add[str]::impl

        At the moment, the implementation is a bit ad-hoc and hackish, as it
        considers ONLY type params as qualifiers, and ignores everything else.

        Note that this is more about readability than correctness: in case of
        blue params which are ignored, we might get clashing namespaces, but
        this is still ok, because uniqueness of FQNs is guaranteed by
        vm.get_unique_FQN().

        This is fine as long as we don't support separate compilation. For sep
        comp, we will probably need a deterministic and reproducible way to
        compute unique FQNs out of a blue call.
        """
        if w_func.color == "red":
            return w_func.fqn
        assert args_w is not None
        ns = w_func.fqn
        quals = []
        for w_arg in args_w:
            if isinstance(w_arg, W_Type):
                quals.append(w_arg.fqn)
        return ns.with_qualifiers(quals)

    def run(self, args_w: Sequence[W_Object]) -> W_Object:
        assert self.w_func.is_valid, "w_func has been redshifted"
        self.declare_arguments()
        self.init_arguments(args_w)
        try:
            # This is suboptimal, but probably good enough for now: do a
            # forward declaration of user-defined types, found by looking at
            # 'classdef' statements. The problem is that by doing this, we
            # don't consider nested classdefs (e.g., if it's inside an
            # if). But even so, it's unclear whether it makes any sense? For
            # example, what should the following code do?
            #   @blue
            #   def foo():
            #       x: S
            #       if random():
            #           class S: ...
            #
            # Is the forward declaration of "S" available or not?  For now, we
            # just ignore the problem and support only classdef done at the
            # outermost level.
            for stmt in self.funcdef.body:
                if isinstance(stmt, ast.ClassDef):
                    self.fwdecl_ClassDef(stmt)

            for stmt in self.funcdef.body:
                self.exec_stmt(stmt)
            #
            # we reached the end of the function. If it's void, we can return
            # None, else it's an error.
            if self.w_func.w_functype.w_restype in (TYPES.w_NoneType, B.w_dynamic):
                return B.w_None
            else:
                loc = self.w_func.funcdef.loc.make_end_loc()
                msg = "reached the end of the function without a `return`"
                raise SPyError.simple("W_TypeError", msg, "no return", loc)

        except Return as e:
            return e.w_value

    def declare_arguments(self) -> None:
        w_ft = self.w_func.w_functype
        funcdef = self.funcdef
        self.declare_local("@if", B.w_bool, Loc.fake())
        self.declare_local("@while", B.w_bool, Loc.fake())
        self.declare_local("@return", w_ft.w_restype, funcdef.return_type.loc)
        self.declare_local("@assert", B.w_bool, Loc.fake())

        assert w_ft.is_argcount_ok(len(funcdef.args))
        for i, param in enumerate(w_ft.params):
            if param.kind == "simple":
                arg = funcdef.args[i]
                self.declare_local(arg.name, param.w_T, arg.loc)

            elif param.kind == "var_positional":
                assert funcdef.vararg is not None
                assert i == len(funcdef.args)
                # XXX: we don't have typed tuples, for now we just use a
                # generic untyped tuple as the type.
                arg = funcdef.vararg
                self.declare_local(arg.name, B.w_tuple, arg.loc)

            else:
                assert False

    def init_arguments(self, args_w: Sequence[W_Object]) -> None:
        """
        Store the arguments in args_w in the appropriate local var
        """
        w_ft = self.w_func.w_functype
        args = self.funcdef.args

        for i, param in enumerate(w_ft.params):
            if param.kind == "simple":
                arg = args[i]
                w_arg = args_w[i]
                self.store_local(arg.name, w_arg)

            elif param.kind == "var_positional":
                assert self.funcdef.vararg is not None
                assert i == len(self.funcdef.args)
                arg = self.funcdef.vararg
                items_w = args_w[i:]
                w_varargs = W_Tuple(list(items_w))
                self.store_local(arg.name, w_varargs)

            else:
                assert False
