from contextlib import contextmanager
from types import NoneType
from typing import TYPE_CHECKING, Iterator, Optional, Sequence

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
from spy.vm.modules.__spy__ import SPY
from spy.vm.modules.operator import OP, OP_from_token, OP_unary_from_token
from spy.vm.modules.operator.convop import CONVERT_maybe
from spy.vm.modules.types import TYPES
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
    loc: Loc
    closure: CLOSURE
    symtable: SymTable
    locals: dict[str, LocalVar]
    specialized_names: dict[ast.Name, ast.Expr]
    specialized_assigns: dict[ast.Assign, ast.Stmt]
    specialized_assignexprs: dict[ast.AssignExpr, ast.Expr]
    desugared_fors: dict[ast.For, tuple[ast.Assign, ast.While]]

    def __init__(
        self, vm: "SPyVM", ns: FQN, loc: Loc, symtable: SymTable, closure: CLOSURE
    ) -> None:
        assert type(self) is not AbstractFrame, "abstract class"
        self.vm = vm
        self.ns = ns
        self.loc = loc
        self.symtable = symtable
        self.closure = closure
        self.locals = {}

        # when we interact with a frame from a SPdb prompt we have slightly different
        # rules, because e.g. we might try to evaluate an ast.Name which is not in the
        # symtable
        self.is_interactive = False

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
        self.specialized_assignexprs = {}
        self.desugared_fors = {}

    # overridden by DopplerFrame
    @property
    def redshifting(self) -> bool:
        return False

    @contextmanager
    def interactive(self) -> Iterator[None]:
        old = self.is_interactive
        self.is_interactive = True
        yield
        self.is_interactive = False

    def get_locals_types_w(self) -> dict[str, W_Type]:
        return {
            name: lv.w_T
            for name, lv in self.locals.items()
            if lv.color == "red"
        }  # fmt: skip

    def declare_local(
        self, name: str, desired_color: Color, w_type: W_Type, loc: Loc
    ) -> None:
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

        # determine the color of the local var:
        #   - varkind is statically known and depends on the symbol
        #   - desired_color is the color of the wam that we determine during execution
        #
        # The local variable will be "blue" IIF varkind is "const" and "desired_color"
        # is actually a "blue". Consider this case:
        #     x = 0                # const, blue
        #     y = some_red_func()  # const, red
        # They are both const, but "y" cannot be "blue" because we don't know its value
        # during redshift.
        if name[0] == "@":
            # special case '@if', '@while', etc.
            color: Color = "red"
        else:
            sym = self.symtable.lookup(name)
            assert sym.is_local
            if sym.varkind == "const" and desired_color == "blue":
                color = "blue"
            else:
                color = "red"
        self.locals[name] = LocalVar(
            varname=name, decl_loc=loc, color=color, w_T=w_type, w_val=None
        )

    def declare_reserved_bool_locals(self) -> None:
        for name in ("@if", "@and", "@or", "@while", "@assert"):
            self.declare_local(name, "red", B.w_bool, Loc.fake())

    def store_local(self, name: str, w_value: W_Object) -> None:
        self.locals[name].w_val = w_value

    def load_local(self, name: str) -> W_Object:
        localvar = self.locals.get(name)
        if localvar is None or localvar.w_val is None:
            raise SPyError("W_Exception", "read from uninitialized local")
        return localvar.w_val

    def exec_stmt(self, stmt: ast.Stmt) -> None:
        return magic_dispatch(self, "exec_stmt", stmt)

    def typecheck_maybe(
        self, wam: W_MetaArg, varname: Optional[str]
    ) -> Optional[W_OpImpl]:
        if varname is None:
            return None  # no typecheck needed
        lv = self.locals[varname]
        w_expT = lv.w_T
        wam_expT = W_MetaArg.from_w_obj(self.vm, lv.w_T, loc=lv.decl_loc)
        try:
            w_typeconv_opimpl = CONVERT_maybe(self.vm, wam_expT, wam)
        except SPyError as err:
            if not err.match(W_TypeError):
                raise

            if varname in ("@if", "@and", "@or", "@while", "@assert"):
                # no need to add extra info
                pass
            elif varname == "@return":
                exp = w_expT.fqn.human_name
                msg = f"expected `{exp}` because of return type"
                loc = self.symtable.lookup(varname).type_loc
                err.add("note", msg, loc=loc)
            else:
                exp = w_expT.fqn.human_name
                msg = f"expected `{exp}` because of type declaration"
                loc = self.symtable.lookup(varname).type_loc
                err.add("note", msg, loc=loc)

            raise
        return w_typeconv_opimpl

    def eval_expr(self, expr: ast.Expr, *, varname: Optional[str] = None) -> W_MetaArg:
        assert not self.redshifting, "DopplerFrame should override eval_expr"
        wam = magic_dispatch(self, "eval_expr", expr)

        w_typeconv_opimpl = self.typecheck_maybe(wam, varname)
        if w_typeconv_opimpl is None:
            # no conversion needed, hooray
            return wam
        else:
            if isinstance(self, ASTFrame):
                # sanity check. After redshifting, all type conversions should be
                # explicit. If w_typeconv is not None here, it means that Doppler failed
                # to insert the appropriate conversion
                assert not self.w_func.redshifted

            # apply the conversion
            assert varname is not None
            lv = self.locals[varname]
            wam_expT = W_MetaArg.from_w_obj(self.vm, lv.w_T, loc=lv.decl_loc)
            wam_gotT = W_MetaArg.from_w_obj(self.vm, wam.w_static_T, loc=wam.loc)
            wam_val = self.vm.eval_opimpl(
                w_typeconv_opimpl,
                [wam_expT, wam_gotT, wam],
                loc=expr.loc,
                redshifting=self.redshifting,
            )
            return wam_val

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
        # if we are defining a function inside a class, it's a method
        is_method = self.symtable.kind == "class"

        # evaluate the functype
        params = []
        for i, arg in enumerate(funcdef.args):
            # evaluate param type. If it's "auto" there are three cases:
            #   1. it's a param of a @blue function
            #   2. it's the "self" of a method
            #   3. it's an error
            is_auto = isinstance(arg.type, ast.Auto)

            if is_auto and funcdef.color == "blue":
                # case (1)
                w_param_type = B.w_dynamic

            elif is_auto and is_method and i == 0:
                # case (2)
                # first arg of a method, it's the "self": we assign it the type of the
                # class which we are currently evaluating
                w_param_type = self.vm.lookup_global(self.ns)

            elif is_auto and funcdef.color == "red":
                # case (3)
                raise SPyError.simple(
                    "W_TypeError",
                    f"missing type for argument '{arg.name}'",
                    "type is missing here",
                    arg.loc,
                )

            else:
                # normal case, no auto
                w_param_type = self.eval_expr_type(arg.type)

            param = FuncParam(w_T=w_param_type, kind=arg.kind)
            params.append(param)

        # evaluate return type
        is_auto = isinstance(funcdef.return_type, ast.Auto)
        if is_auto and funcdef.color == "red":
            raise SPyError.simple(
                "W_TypeError", "missing return type", "", funcdef.return_type.loc
            )
        elif is_auto and funcdef.color == "blue":
            w_restype = B.w_dynamic
        else:
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
                if wam_inner.color != "blue":
                    err = SPyError("W_TypeError", "decorators must be @blue")
                    err.add("error", "this is red", deco.loc)
                    raise err
                assert wam_inner.color == "blue"
                w_func = wam_inner.w_blueval

        w_T = self.vm.dynamic_type(w_func)
        self.declare_local(funcdef.name, "blue", w_T, funcdef.prototype_loc)
        self.store_local(funcdef.name, w_func)

    @staticmethod
    def metaclass_for_classdef(classdef: ast.ClassDef) -> type[W_Type]:
        if classdef.kind == "struct":
            return W_StructType
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
        self.declare_local(classdef.name, "blue", w_meta_type, classdef.loc)
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
            self.declare_local(varname, "red", w_T, vardef.loc)
            return

        if is_auto:
            # type inference
            wam = self.eval_expr(vardef.value)
            color = wam.color
            w_T = wam.w_static_T
            self.declare_local(varname, color, w_T, vardef.loc)
        else:
            # definition
            w_T = self.eval_expr_type(vardef.type)
            self.declare_local(varname, "red", w_T, vardef.loc)
            wam = self.eval_expr(vardef.value, varname=varname)
            # XXX hack hack hack: would be nice to find a way to avoid mutating
            # LocalVar. Ideally we would like to write something like this:
            #     wam = self.eval_expr(vardef.value, varname=varname)
            #     self.declare_local(varname, wam.color, ...)
            #
            # However, we cannot do that, because declare_local must be called BEFORE
            # eval_expr (because of varname=varname). If we remove varname=varname it
            # probably works, but we lose good error message.
            if sym.varkind == "const":
                self.locals[varname].color = wam.color

        # store the value (common for "type inference" and "definition")
        lv = self.locals[varname]
        if not self.redshifting or lv.color == "blue":
            self.store_local(varname, wam.w_val)

    def exec_stmt_Assign(self, assign: ast.Assign) -> None:
        # see the commnet in __init__ about specialized_assigns
        specialized = self.specialized_assigns.get(assign)
        if specialized is None:
            specialized = self._specialize_Assign(assign)
            self.specialized_assigns[assign] = specialized
        self.exec_stmt(specialized)

    def _specialize_assign_common(
        self, loc: Loc, target: ast.StrConst, value: ast.Expr, expr: bool
    ) -> ast.AssignLocal | ast.AssignCell | ast.AssignExprLocal | ast.AssignExprCell:
        varname = target.value
        sym = self.symtable.lookup(varname)

        if sym.varkind == "const" and sym.varkind_origin != "auto":
            err = SPyError("W_TypeError", "invalid assignment target")
            err.add("error", f"{sym.name} is const", target.loc)
            err.add("note", f"const declared here ({sym.varkind_origin})", sym.loc)

            if sym.varkind_origin == "global-const":
                msg = f"help: declare it as variable: `var {sym.name} ...`"
                err.add("note", msg, sym.loc)
            elif sym.varkind_origin == "blue-param":
                msg = "blue function arguments are const by default"
                err.add("note", msg, sym.loc)

            raise err
        elif sym.storage == "direct":
            assert sym.is_local
            if expr:
                return ast.AssignExprLocal(loc, target, value)
            else:
                return ast.AssignLocal(loc, target, value)

        elif sym.storage == "cell":
            outervars = self.closure[-sym.level]
            w_cell = outervars[sym.name].w_val
            assert isinstance(w_cell, W_Cell)
            if expr:
                return ast.AssignExprCell(
                    loc=loc,
                    target=target,
                    target_fqn=w_cell.fqn,
                    value=value,
                )
            else:
                return ast.AssignCell(
                    loc=loc,
                    target=target,
                    target_fqn=w_cell.fqn,
                    value=value,
                )

        else:
            assert False

    def _specialize_Assign(self, assign: ast.Assign) -> ast.Stmt:
        res = self._specialize_assign_common(
            loc=assign.loc, target=assign.target, value=assign.value, expr=False
        )
        assert isinstance(res, (ast.AssignLocal, ast.AssignCell))
        return res

    def _specialize_AssignExpr(self, assignexpr: ast.AssignExpr) -> ast.Expr:
        res = self._specialize_assign_common(
            loc=assignexpr.loc,
            target=assignexpr.target,
            value=assignexpr.value,
            expr=True,
        )
        assert isinstance(res, (ast.AssignExprLocal, ast.AssignExprCell))
        return res

    def exec_stmt_AssignLocal(self, assign: ast.AssignLocal) -> None:
        self._execute_AssignLocal(assign.target, assign.value)

    def _execute_AssignLocal(self, target: ast.StrConst, value: ast.Expr) -> W_MetaArg:
        varname = target.value
        lv = self.locals.get(varname)
        if lv is None:
            # first assignment, implicit declaration
            wam = self.eval_expr(value)
            self.declare_local(varname, wam.color, wam.w_static_T, target.loc)
            lv = self.locals[varname]
        else:
            wam = self.eval_expr(value, varname=varname)

        if not self.redshifting or lv.color == "blue":
            self.store_local(varname, wam.w_val)
        return wam

    def exec_stmt_AssignCell(self, assign: ast.AssignCell) -> None:
        self._execute_AssignCell(assign.target, assign.target_fqn, assign.value)

    def _execute_AssignCell(
        self, target: ast.StrConst, target_fqn: FQN, value: ast.Expr
    ) -> W_MetaArg:
        wam = self.eval_expr(value)
        if not self.redshifting:
            w_cell = self.vm.lookup_global(target_fqn)
            assert isinstance(w_cell, W_Cell)
            w_cell.set(wam.w_val)
        return wam

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

        if wam_tup.color == "red" and self.symtable.color == "red":
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

    def eval_expr_Auto(self, auto: ast.Auto) -> W_MetaArg:
        raise SPyError.simple(
            "W_TypeError",
            "Interal SPy error: ast.Auto expressions should be handled case-by-case",
            "this is `auto`",
            auto.loc,
        )

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
        if not self.is_interactive:
            assert sym is not None

        if sym is None:
            # sym can be None ONLY in interactive frames (in which case we do a dynamic
            # lookup), else it means that there is a bug in symtable.
            assert self.is_interactive, "sym not found"
            # create a fake symbol to be used below
            sym = Symbol(
                varname,
                "var",
                "auto",
                "NameError",
                loc=name.loc,
                type_loc=name.loc,
                level=-1,
            )

        if sym.impref is not None:
            return ast.NameImportRef(name.loc, sym)
        elif sym.is_local:
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

    def eval_expr_NameImportRef(self, name: ast.NameImportRef) -> W_MetaArg:
        # this is correct as long as we import 'const', but if we import 'var', then it
        # should probably be red? For now, we just don't support it.
        color: Color = "blue"
        sym = name.sym
        assert sym.impref is not None
        w_val = self.vm.lookup_ImportRef(sym.impref)
        # XXX: this should be an ImportError?
        assert w_val is not None
        if isinstance(w_val, W_Cell):
            raise SPyError.simple(
                "W_WIP",
                "cannot import `var` and/or `cell`",
                "this is `cell`",
                name.loc,
            )
        w_T = self.vm.dynamic_type(w_val)
        return W_MetaArg(self.vm, color, w_T, w_val, name.loc, sym=sym)

    def eval_expr_NameLocal(self, name: ast.NameLocal) -> W_MetaArg:
        sym = name.sym
        lv = self.locals[sym.name]
        if lv.color == "red" and self.redshifting:
            w_val = None
        else:
            w_val = self.load_local(sym.name)
        return W_MetaArg(self.vm, lv.color, lv.w_T, w_val, name.loc, sym=sym)

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
        color: Color = "blue" if sym.varkind == "const" else "red"
        return W_MetaArg(self.vm, color, w_T, w_val, name.loc, sym=sym)

    def eval_expr_AssignExpr(self, assignexpr: ast.AssignExpr) -> W_MetaArg:
        specialized = self.specialized_assignexprs.get(assignexpr)
        if specialized is None:
            specialized = self._specialize_AssignExpr(assignexpr)
            self.specialized_assignexprs[assignexpr] = specialized
        if isinstance(specialized, ast.AssignExprLocal):
            return self._set_assignexpr_color(
                specialized.target,
                self._execute_AssignLocal(specialized.target, specialized.value),
            )
        elif isinstance(specialized, ast.AssignExprCell):
            return self._set_assignexpr_color(
                specialized.target,
                self._execute_AssignCell(
                    specialized.target, specialized.target_fqn, specialized.value
                ),
            )
        else:
            assert False

    def eval_expr_AssignExprLocal(self, assignexpr: ast.AssignExprLocal) -> W_MetaArg:
        return self._set_assignexpr_color(
            assignexpr.target,
            self._execute_AssignLocal(assignexpr.target, assignexpr.value),
        )

    def eval_expr_AssignExprCell(self, assignexpr: ast.AssignExprCell) -> W_MetaArg:
        return self._set_assignexpr_color(
            assignexpr.target,
            self._execute_AssignCell(
                assignexpr.target, assignexpr.target_fqn, assignexpr.value
            ),
        )

    def _set_assignexpr_color(self, target: ast.StrConst, wam: W_MetaArg) -> W_MetaArg:
        sym = self.symtable.lookup(target.value)
        if sym.varkind == "var":
            return wam.as_red(self.vm)
        return wam

    def eval_opimpl(
        self,
        op: ast.Node,
        w_opimpl: W_OpImpl,
        args_wam: list[W_MetaArg],
    ) -> W_MetaArg:
        """
        Note: this is overrided by DopplerFrame to remember the w_opimpl.
        """
        return self.vm.eval_opimpl(
            w_opimpl,
            args_wam,
            loc=op.loc,
            redshifting=self.redshifting,
        )

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

    def _ensure_bool(self, wam: W_MetaArg) -> W_MetaArg:
        wam_expT = W_MetaArg.from_w_obj(self.vm, B.w_bool)
        w_typeconv_opimpl = CONVERT_maybe(self.vm, wam_expT, wam)
        if w_typeconv_opimpl is None:
            return wam
        return self.vm.eval_opimpl(
            w_typeconv_opimpl,
            [wam_expT, wam],
            loc=wam.loc,
            redshifting=False,  # we want to always execute this eagerly
        )

    def eval_expr_And(self, op: ast.And) -> W_MetaArg:
        if self.redshifting:
            wam_l = self.eval_expr(op.left, varname="@and")
            wam_r = self.eval_expr(op.right, varname="@and")
            color = maybe_blue(wam_l.color, wam_r.color)
            if color == "blue":
                w_left_bool = self._ensure_bool(wam_l)
                w_right_bool = self._ensure_bool(wam_r)
                w_val = self.vm.wrap(
                    self.vm.unwrap_bool(w_left_bool.w_val)
                    and self.vm.unwrap_bool(w_right_bool.w_val),
                )
            else:
                w_val = None
            return W_MetaArg(self.vm, color, B.w_bool, w_val, op.loc)

        wam_l = self.eval_expr(op.left, varname="@and")
        w_left = wam_l.w_val
        if not self.vm.unwrap_bool(w_left):
            return wam_l
        wam_r = self.eval_expr(op.right, varname="@and")
        return wam_r

    def eval_expr_Or(self, op: ast.Or) -> W_MetaArg:
        if self.redshifting:
            wam_l = self.eval_expr(op.left, varname="@or")
            wam_r = self.eval_expr(op.right, varname="@or")
            color = maybe_blue(wam_l.color, wam_r.color)
            if color == "blue":
                w_left_bool = self._ensure_bool(wam_l)
                w_right_bool = self._ensure_bool(wam_r)
                w_val = self.vm.wrap(
                    self.vm.unwrap_bool(w_left_bool.w_val)
                    or self.vm.unwrap_bool(w_right_bool.w_val),
                )
            else:
                w_val = None
            return W_MetaArg(self.vm, color, B.w_bool, w_val, op.loc)

        wam_l = self.eval_expr(op.left, varname="@or")
        w_left = wam_l.w_val
        if self.vm.unwrap_bool(w_left):
            return wam_l
        wam_r = self.eval_expr(op.right, varname="@or")
        return wam_r

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

    def eval_expr_List(self, lst: ast.List) -> W_MetaArg:
        # 0. empty lists are special
        if len(lst.items) == 0:
            w_T = SPY.w_EmptyListType
            w_val = SPY.w_empty_list
            return W_MetaArg(self.vm, "red", w_T, w_val, lst.loc)

        # 1. evaluate the individual items and infer the itemtype
        items_wam = []
        w_itemtype = None
        color: Color = "red"  # XXX should be blue?
        for item in lst.items:
            wam_item = self.eval_expr(item)

            # This is needed when building a list[MetaArg].
            #
            # If we have two blue items which happen to be equal, we reuse the same
            # w_opimpl for push() below, with the result of pushing the first item
            # twice, and the second item never. By making it red, we force to create a
            # more generic opimpl.
            #
            # See also:
            #    test_list::test_list_MetaArg_identity
            #    typecheck_opspec, big comment starting with "THIS IS PROBABLY A BUG".
            wam_item = wam_item.as_red(self.vm)

            items_wam.append(wam_item)
            color = maybe_blue(color, wam_item.color)
            if w_itemtype is None:
                w_itemtype = wam_item.w_static_T
            w_itemtype = self.vm.union_type(w_itemtype, wam_item.w_static_T)
        assert w_itemtype is not None

        # 2. instantiate a new list
        w_ListType = self.vm.lookup_global(FQN("_list::list"))
        w_T = self.vm.getitem_w(w_ListType, w_itemtype, loc=lst.loc)  # list[i32]
        wam_T = W_MetaArg.from_w_obj(self.vm, w_T)

        w_opimpl = self.vm.call_OP(lst.loc, OP.w_CALL, [wam_T])
        wam_list = self.eval_opimpl(lst, w_opimpl, [wam_T])

        # 3. push items into the list
        assert isinstance(w_T, W_Type)
        fqn_push = w_T.fqn.join("_push")
        w_push = self.vm.lookup_global(fqn_push)
        wam_push = W_MetaArg.from_w_obj(self.vm, w_push)

        for item, wam_item in zip(lst.items, items_wam):
            w_opimpl = self.vm.call_OP(
                lst.loc, OP.w_CALL, [wam_push, wam_list, wam_item]
            )
            wam_list = self.eval_opimpl(item, w_opimpl, [wam_push, wam_list, wam_item])

        return wam_list

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
        assert w_func.funcdef.symtable.kind == "function"
        # if w_func was redshifted, automatically use the new version
        if w_func.w_redshifted_into:
            w_func = w_func.w_redshifted_into
        assert isinstance(w_func, W_ASTFunc)
        ns = self.compute_ns(w_func, args_w)
        super().__init__(
            vm, ns, w_func.funcdef.loc, w_func.funcdef.symtable, w_func.closure
        )
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
        self.declare_reserved_bool_locals()
        self.declare_local("@return", "red", w_ft.w_restype, funcdef.return_type.loc)

        color = self.w_func.color
        assert w_ft.is_argcount_ok(len(funcdef.args))
        for i, param in enumerate(w_ft.params):
            arg = funcdef.args[i]
            if param.kind == "simple":
                self.declare_local(arg.name, color, param.w_T, arg.loc)

            elif param.kind == "var_positional":
                # XXX: we don't have typed tuples, for now we just use a
                # generic untyped tuple as the type.
                assert i == len(funcdef.args) - 1
                self.declare_local(arg.name, color, B.w_tuple, arg.loc)

            else:
                assert False

    def init_arguments(self, args_w: Sequence[W_Object]) -> None:
        """
        Store the arguments in args_w in the appropriate local var
        """
        w_ft = self.w_func.w_functype

        for i, param in enumerate(w_ft.params):
            if param.kind == "simple":
                arg = self.funcdef.args[i]
                w_arg = args_w[i]
                self.store_local(arg.name, w_arg)

            elif param.kind == "var_positional":
                assert i == len(self.funcdef.args) - 1
                arg = self.funcdef.args[i]
                items_w = args_w[i:]
                w_varargs = W_Tuple(list(items_w))
                self.store_local(arg.name, w_varargs)

            else:
                assert False
