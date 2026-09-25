from ctypes import c_float as float32
from types import NoneType
from typing import TYPE_CHECKING, Never, Optional, Sequence

from fixedint import Int8, Int32, Int64, UInt8, UInt32, UInt64

from spy import ast
from spy.analyze.sym import Color, FrameInfo, Symbol, maybe_blue
from spy.errors import WIP, SPyError
from spy.fqn import FQN
from spy.location import Loc
from spy.util import magic_dispatch
from spy.vm.b import B
from spy.vm.cell import W_Cell
from spy.vm.exc import W_NameError, W_TypeError
from spy.vm.function import CLOSURE, FuncParam, LocalVar, W_ASTFunc, W_Func, W_FuncType
from spy.vm.modules.__spy__ import SPY
from spy.vm.modules.__spy__.interp_tuple import W_InterpTuple
from spy.vm.modules.operator import OP, OP_from_token, OP_unary_from_token
from spy.vm.modules.operator.convop import CONVERT_maybe
from spy.vm.modules.types import TYPES
from spy.vm.object import W_Object, W_Type
from spy.vm.opimpl import W_OpImpl
from spy.vm.opspec import W_MetaArg
from spy.vm.primitive import W_Bool
from spy.vm.struct import W_StructType
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
    frameinfo: FrameInfo
    locals: dict[str, LocalVar]
    special_calls: dict[ast.Call, str]
    # stack of currently-entered Blocks; used by spdb to interactively resolve names
    block_stack: list[ast.Block]

    def __init__(
        self, vm: "SPyVM", ns: FQN, loc: Loc, frameinfo: FrameInfo, closure: CLOSURE
    ) -> None:
        assert type(self) is not AbstractFrame, "abstract class"
        self.vm = vm
        self.ns = ns
        self.loc = loc
        self.frameinfo = frameinfo
        self.closure = closure
        # TODO: once the scope migration is done, we know all the slots in advance
        # (from the frameinfo), so we could pre-initialize self.locals with the right
        # slots instead of populating it lazily via declare_local.
        self.locals = {}
        self.special_calls = {}
        self.block_stack = []

    # overridden by DopplerFrame
    @property
    def redshifting(self) -> bool:
        return False

    def get_locals_types_w(self) -> dict[str, W_Type]:
        res = {}
        for name, lv in self.locals.items():
            if lv.color == "red":
                assert lv.w_T is not None
                res[name] = lv.w_T
        return res

    def declare_local(
        self, name: str, desired_color: Color, w_type: Optional[W_Type], loc: Loc
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

        if w_type is not None and not isinstance(w_type, W_FuncType):
            self.vm.make_fqn_const(w_type)

        # determine the color of the local var:
        #   - varkind is statically known and depends on the symbol
        #   - desired_color is the color of the wam that we determine during execution
        #
        # The local variable will be "blue" IF varkind is "const" and "desired_color"
        # is actually a "blue". Consider this case:
        #     x = 0                # const, blue
        #     y = some_red_func()  # const, red
        # They are both const, but "y" cannot be "blue" because we don't know its value
        # during redshift.
        if name[0] == "@" or name == "__extra_fields__":
            # special case '@if', '@while', etc.
            color: Color = "red"
        else:
            sym = self.frameinfo.lookup(name)
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
        lv = self.locals[name]
        if lv.w_T is None:
            # deferred type inference, see exec_stmt_VarDef
            lv.w_T = self.vm.dynamic_type(w_value)
        # sanity check
        if isinstance(w_value, W_Cell):
            assert self.vm.isinstance(w_value.get(), lv.w_T)
        else:
            assert self.vm.isinstance(w_value, lv.w_T)
        lv.w_val = w_value

    def fix_deferred_inference_type(self, name: str, w_T: W_Type) -> None:
        """
        Fix the type of a local declared as `var x: auto` with no initializer.
        Called on the first assignment to that variable.
        Subclasses (DopplerFrame) may override to also patch the deferred VarDef node.
        """
        self.locals[name].w_T = w_T

    def load_local(self, name: str) -> W_Object:
        localvar = self.locals.get(name)
        if localvar is None or localvar.w_val is None:
            raise SPyError("W_Exception", "read from uninitialized local")
        return localvar.w_val

    def exec_stmt(self, stmt: ast.Stmt) -> None:
        return magic_dispatch(self, "exec_stmt", stmt)

    def exec_Block(self, block: ast.Block) -> None:
        # Entering a Block is the single, centralized place where we push/pop the
        # runtime block stack. Every body (funcdef/if/while/for) routes through
        # here, so the push/pop cannot be forgotten and survives
        # Break/Continue/Return/exceptions (finally).
        self.block_stack.append(block)
        try:
            for stmt in block.body:
                self.exec_stmt(stmt)
        finally:
            self.block_stack.pop()

    def typecheck_maybe(
        self, wam: W_MetaArg, varname: Optional[str]
    ) -> Optional[W_OpImpl]:
        if varname is None:
            return None  # no typecheck needed
        lv = self.locals[varname]
        assert lv.w_T is not None
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
                exp = w_expT.fqn.human_name(self.vm)
                msg = f"expected `{exp}` because of return type"
                loc = self.frameinfo.lookup(varname).type_loc
                err.add("note", msg, loc=loc)
            else:
                exp = w_expT.fqn.human_name(self.vm)
                msg = f"expected `{exp}` because of type declaration"
                loc = self.frameinfo.lookup(varname).type_loc
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
                assert self.w_func.stage == "astcompiled"

            # apply the conversion
            assert varname is not None
            lv = self.locals[varname]
            assert lv.w_T is not None
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
        got = w_valtype.fqn.human_name(self.vm)
        msg = f"expected `type`, got `{got}`"
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
        is_method = self.frameinfo.kind == "class"

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
        # XXX we should capture only the names actually used in the inner func
        if self.frameinfo.kind == "class":
            # [name.class-skip]: symbols in the class frame cannot be captured by inner
            # methods, do we don't need to save it in the closure.  See also
            # Scope.lookup.
            closure = self.closure
        else:
            closure = self.closure + (self.locals,)

        # this is just a cosmetic nicety. In presence of decorators, "mod.foo"
        # will NOT necessarily contain the function object which is being
        # created. If we call the function FQN("mod::foo"), it might create
        # confusion. The solution is that in presence of decorators, we use
        # FQN("mod::foo#__bare__") as the name of the function, to make it
        # clear is the undecorated version.
        #
        # We must append "#__bare__" BEFORE calling get_unique_FQN, otherwise
        # when the same FuncDef is re-entered (e.g. multiple instantiations of
        # an enclosing @blue.generic) we'd get the un-suffixed FQN as "unique"
        # and then collide on the suffixed version.
        if funcdef.decorators:
            fqn = fqn.with_suffix("__bare__")
        fqn = self.vm.get_unique_FQN(fqn)

        defaults_w = [self.eval_expr(d).w_val for d in funcdef.defaults]
        w_func: W_Object = W_ASTFunc(
            w_functype,
            fqn,
            funcdef,
            closure,
            defaults_w=defaults_w,
            stage="astcompiled",
        )
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
        slot_name = funcdef.sym.slot_name
        self.declare_local(slot_name, "blue", w_T, funcdef.prototype_loc)
        self.store_local(slot_name, w_func)

    def exec_stmt_GenericFuncDef(self, gfuncdef: ast.GenericFuncDef) -> None:
        """
        Desugar generic argument syntax sugar:

            def add[T](a0: T, a1: T) -> T:
                return a0 + a1

        into the equivalent of:

            @blue.generic
            def add(T):
                def __impl(a0: T, a1: T) -> T:
                    return a0 + a1
                return __impl
        """
        loc = gfuncdef.loc

        # build synthetic return: return __impl
        impl_symbol = gfuncdef.frameinfo.lookup("__impl")
        return_stmt = ast.Return(
            loc=loc,
            value=ast.NameLocalDirect(loc=loc, sym=impl_symbol),
        )

        outer_funcdef = ast.FuncDef(
            loc=loc,
            stage="astcompiled",
            color="blue",
            kind="generic",
            name=gfuncdef.name,
            args=gfuncdef.args,
            return_type=ast.Auto(loc),
            defaults=[],
            docstring=None,
            scoping_rules="strict",
            body=ast.Block(
                loc=loc,
                body=[gfuncdef.inner, return_stmt],
            ),
            decorators=[],
            _frameinfo=gfuncdef.frameinfo,
        )

        self.exec_stmt_FuncDef(outer_funcdef)

    @staticmethod
    def metaclass_for_classdef(classdef: ast.ClassDef) -> type[W_Type]:
        if classdef.kind == "struct":
            return W_StructType
        else:
            raise SPyError.simple(
                "W_WIP",
                "only @struct classes are supported for now",
                "class defined here",
                classdef.loc,
            )

    def fwdecl_ClassDef(self, classdef: ast.ClassDef) -> None:
        """
        Create a forward-declaration for the given classdef
        """
        # the FQN uses the src name; the local slot uses the (maybe mangled) slot_name
        fqn = self.ns.join(classdef.name)
        fqn = self.vm.get_unique_FQN(fqn)
        pyclass = self.metaclass_for_classdef(classdef)
        w_typedecl = pyclass.declare(fqn)
        w_meta_type = self.vm.dynamic_type(w_typedecl)
        slot_name = classdef.sym.slot_name
        self.declare_local(slot_name, "blue", w_meta_type, classdef.loc)
        self.store_local(slot_name, w_typedecl)
        self.vm.add_global(fqn, w_typedecl)

    def exec_stmt_ClassDef(self, classdef: ast.ClassDef) -> None:
        from spy.vm.classframe import ClassFrame

        # we are DEFINING a type which has already been declared by
        # fwdecl_ClassDef. Look it up
        slot_name = classdef.sym.slot_name
        w_T = self.load_local(slot_name)
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

    def exec_stmt_GenericClassDef(self, gclassdef: ast.GenericClassDef) -> None:
        """
        Desugar generic argument syntax sugar:

            @struct
            class Point[T]:
                x: T

        into the equivalent of:

            @blue.generic
            def Point(T):
                @struct
                class Self:
                    x: T
                return Self
        """
        loc = gclassdef.loc

        # build synthetic return: return Self
        impl_symbol = gclassdef.frameinfo.lookup("Self")
        return_stmt = ast.Return(
            loc=loc,
            value=ast.NameLocalDirect(loc=loc, sym=impl_symbol),
        )

        outer_funcdef = ast.FuncDef(
            loc=loc,
            stage="astcompiled",
            color="blue",
            kind="generic",
            name=gclassdef.name,
            args=gclassdef.args,
            return_type=ast.Auto(loc),
            defaults=[],
            docstring=None,
            scoping_rules="strict",
            body=ast.Block(
                loc=loc,
                body=[gclassdef.inner, return_stmt],
            ),
            decorators=[],
            _frameinfo=gclassdef.frameinfo,
        )

        self.exec_stmt_FuncDef(outer_funcdef)

    def exec_stmt_VarDef(self, vardef: ast.VarDef) -> None:
        # Possible cases:
        #   declaration    (not is_auto and not value):  [var] x: i32
        #   definition     (not is_auto and value):      [var] x: i32 = 0
        #   type inference (is_auto and value):          var   x      = 0
        #   deferred inf.  (is_auto and not value):      var   x: auto
        #
        # Note that the "type inference" case is basically a simple Assign.
        sym = vardef.sym
        varname = sym.slot_name
        # [scope.loop-fresh]: if we have a VarDef inside a loop, it needs to be
        # reinitialized at each iteration
        self.locals.pop(varname, None)
        is_auto = isinstance(vardef.type, ast.Auto)

        if vardef.value is None:
            if is_auto:
                # deferred inference, type will be fixed on first assignment
                # see also eval_expr_AssignExprLocal
                self.declare_local(varname, "red", None, vardef.loc)
            else:
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

    def exec_stmt_AssignLocal(self, assign: ast.AssignLocal) -> None:
        self.eval_expr(assign.expr)

    def exec_stmt_AssignCell(self, assign: ast.AssignCell) -> None:
        self.eval_expr(assign.expr)

    def exec_stmt_AssignUnpack(self, assign: ast.AssignUnpack) -> None:
        wam_tup = self.eval_expr(assign.value)
        w_T = wam_tup.w_static_T

        is_interp_tuple = w_T is SPY.w_interp_tuple
        is_stdlib_tuple = self.vm.is_tuple_type(w_T)
        if not (is_interp_tuple or is_stdlib_tuple):
            t = wam_tup.w_static_T.fqn.human_name(self.vm)
            err = SPyError(
                "W_TypeError",
                f"`{t}` does not support unpacking",
            )
            err.add("error", f"this is `{t}`", assign.value.loc)
            raise err

        if is_interp_tuple:
            w_tup = wam_tup.w_val
            assert isinstance(w_tup, W_InterpTuple)
            got = len(w_tup.items_w)
        else:
            assert isinstance(w_T, W_StructType)
            got = len(list(w_T.iterfields_w()))

        exp = len(assign.targets)
        if exp != got:
            targets_loc = Loc.combine(
                start=assign.targets[0].loc,
                end=assign.targets[-1].loc,
            )
            err = SPyError(
                "W_TypeError",
                f"Wrong number of values to unpack",
            )
            exp_values = maybe_plural(exp, "value")
            got_values = maybe_plural(got, "value")
            err.add("error", f"expected {exp} {exp_values}", targets_loc)
            err.add("error", f"got {got} {got_values}", assign.value.loc)
            raise err

        for i, target in enumerate(assign.targets):
            getitem = ast.GetItem(
                loc=assign.value.loc,
                value=assign.value,
                args=[ast.Literal(loc=assign.value.loc, value=i)],
            )
            assign_expr = ast.AssignExprLocal(
                loc=target.loc,
                target=target,
                sym=self.frameinfo.lookup(target.value),
                value=getitem,
            )
            self.eval_expr_AssignExprLocal(assign_expr)

    def exec_stmt_AugAssign(self, node: ast.AugAssign) -> None:
        # XXX: eventually we want to support things like __IADD__ etc, but for
        # now we just delegate to _ADD__.
        assign = self._desugar_AugAssign(node)
        self.exec_stmt(assign)

    def _desugar_AugAssign(self, node: ast.AugAssign) -> ast.Assign:
        # transform "x += 1" into "x = x + 1"
        return ast.Assign(
            loc=node.loc,
            target=ast.SingleTarget(node.loc, node.target),
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
            self.exec_Block(if_node.then)
        else:
            self.exec_Block(if_node.else_)

    def exec_stmt_While(self, while_node: ast.While) -> None:
        while True:
            wam_cond = self.eval_expr(while_node.test, varname="@while")
            assert isinstance(wam_cond.w_val, W_Bool)
            if self.vm.is_False(wam_cond.w_val):
                break
            try:
                self.exec_Block(while_node.body)
            except Break:
                break
            except Continue:
                continue

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
                    got = wam_msg.w_static_T.fqn.human_name(self.vm)
                    err.add("error", f"expected `str`, got `{got}`", loc=wam_msg.loc)
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
            "Internal SPy error: ast.Auto expressions should be handled case-by-case",
            "this is `auto`",
            auto.loc,
        )

    def eval_expr_Const(self, const: ast.Const) -> W_MetaArg:
        assert const.w_T is not None
        return W_MetaArg(self.vm, "blue", const.w_T, const.w_val, const.loc)

    def eval_expr_Literal(self, lit: ast.Literal) -> W_MetaArg:
        # unsupported literals are rejected directly by the parser, see
        # Parser.from_py_expr_Literal
        val = lit.value
        T = type(val)
        assert T in (
            int,
            float,
            float32,
            complex,
            bool,
            NoneType,
            Int8,
            UInt8,
            Int32,
            UInt32,
            Int64,
            UInt64,
        )
        if T is int and not (Int32.minval <= val <= Int32.maxval):  # type: ignore
            # unprefixed int literals default to i32: let's raise a helpful error
            # message if we are out of range.
            raise SPyError.simple(
                "W_ValueError",
                f"integer literal {val} is out of range for i32; "
                f"use i64({val}) or u64({val}) to get a 64-bit value",
                "integer literal out of range",
                lit.loc,
            )
        w_val = self.vm.wrap(val)
        w_T = self.vm.dynamic_type(w_val)
        return W_MetaArg(self.vm, "blue", w_T, w_val, lit.loc)

    def eval_expr_StrLiteral(self, lit: ast.StrLiteral) -> W_MetaArg:
        w_val = self.vm.wrap(lit.value)
        return W_MetaArg(self.vm, "blue", B.w_str, w_val, lit.loc)

    def eval_expr_BytesLiteral(self, lit: ast.BytesLiteral) -> W_MetaArg:
        w_val = self.vm.wrap(lit.value)
        return W_MetaArg(self.vm, "blue", B.w_bytes, w_val, lit.loc)

    def eval_expr_FQNConst(self, const: ast.FQNConst) -> W_MetaArg:
        w_value = self.vm.lookup_global(const.fqn)
        assert w_value is not None
        return W_MetaArg.from_w_obj(self.vm, w_value)

    def eval_expr_PoisonExpr(self, node: ast.PoisonExpr) -> W_MetaArg:
        raise node.err

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

    def eval_expr_NameLocalDirect(self, name: ast.NameLocalDirect) -> W_MetaArg:
        sym = name.sym
        lv = self.locals[sym.slot_name]
        if lv.color == "red" and self.redshifting:
            w_val = None
        else:
            w_val = self.load_local(sym.slot_name)
        assert lv.w_T is not None
        return W_MetaArg(self.vm, lv.color, lv.w_T, w_val, name.loc, sym=sym)

    def eval_expr_NameLocalCell(self, name: ast.NameLocalCell) -> W_MetaArg:
        sym = name.sym
        lv = self.locals[sym.slot_name]
        if lv.color == "red" and self.redshifting:
            w_val = None
        else:
            w_cell = self.load_local(sym.slot_name)
            assert isinstance(w_cell, W_Cell)
            w_val = w_cell.get()
        assert lv.w_T is not None
        return W_MetaArg(self.vm, lv.color, lv.w_T, w_val, name.loc, sym=sym)

    def eval_expr_NameOuterDirect(self, name: ast.NameOuterDirect) -> W_MetaArg:
        color: Color = "blue"  # closed-over variables are always blue
        sym = name.sym
        assert not sym.is_local
        outervars = self.closure[-sym.frame_depth]
        w_val = outervars[sym.slot_name].w_val
        assert w_val is not None
        w_T = self.vm.dynamic_type(w_val)
        return W_MetaArg(self.vm, color, w_T, w_val, name.loc, sym=sym)

    def eval_expr_NameOuterCell(self, name: ast.NameOuterCell) -> W_MetaArg:
        sym = name.sym
        assert not sym.is_local
        w_cell: Optional[W_Object]
        if name.fqn is not None:
            w_cell = self.vm.lookup_global(name.fqn)
        else:
            outervars = self.closure[-sym.frame_depth]
            w_cell = outervars[sym.slot_name].w_val
        assert isinstance(w_cell, W_Cell)
        w_val = w_cell.get()
        w_T = self.vm.dynamic_type(w_val)
        color: Color = "blue" if sym.varkind == "const" else "red"
        return W_MetaArg(self.vm, color, w_T, w_val, name.loc, sym=sym)

    def eval_expr_BlockExpr(self, block: ast.BlockExpr) -> W_MetaArg:
        for stmt in block.body:
            self.exec_stmt(stmt)
        return self.eval_expr(block.value)

    def eval_expr_AssignExprLocal(self, assign: ast.AssignExprLocal) -> W_MetaArg:
        target = assign.target
        value = assign.value
        varname = assign.sym.slot_name

        lv = self.locals.get(varname)
        if lv is None:
            # first assignment, implicit declaration
            wam = self.eval_expr(value)
            self.declare_local(varname, wam.color, wam.w_static_T, target.loc)
            lv = self.locals[varname]
        elif lv.w_T is None:
            # deferred type inference: var x: auto with no initializer
            wam = self.eval_expr(value)
            lv.color = wam.color if assign.sym.varkind == "const" else "red"
            self.fix_deferred_inference_type(varname, wam.w_static_T)
        else:
            wam = self.eval_expr(value, varname=varname)

        if not self.redshifting or lv.color == "blue":
            self.store_local(varname, wam.w_val)

        if assign.sym.varkind == "var":
            return wam.as_red(self.vm)
        return wam

    def eval_expr_AssignExprCell(self, assign: ast.AssignExprCell) -> W_MetaArg:
        target_fqn = assign.target_fqn
        value = assign.value
        sym = assign.sym

        wam = self.eval_expr(value)
        if not self.redshifting:
            w_cell: Optional[W_Object]
            if target_fqn is not None:
                w_cell = self.vm.lookup_global(target_fqn)
            else:
                outervars = self.closure[-sym.frame_depth]
                w_cell = outervars[sym.slot_name].w_val
            assert isinstance(w_cell, W_Cell)
            w_cell.set(wam.w_val)

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
        Note: this is overridden by DopplerFrame to remember the w_opimpl.
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

        # special case getattr, hasattr and setattr: if we arrive at this point it means that the
        # call typed correctly (right number, type and color of arguments). The returned
        # opimpl is not supposed to be executed, see builtins.w_getattr.
        #
        # Instead, we pretend to be ast.GetAttr or ast.SetAttr: this ensures that we get
        # nice error messages like "type `X` has not attribute 'y'".  See also the
        # corresponding code in DopplerFrame.shift_expr_Call.
        if wam_func.color == "blue" and wam_func.w_blueval is B.w_getattr:
            self.special_calls[call] = "getattr"
            w_opimpl = self.vm.call_OP(call.loc, OP.w_GETATTR, args_wam)
            return self.eval_opimpl(call, w_opimpl, args_wam)

        elif wam_func.color == "blue" and wam_func.w_blueval is B.w_hasattr:
            self.special_calls[call] = "hasattr"
            w_opimpl = self.vm.call_OP(call.loc, OP.w_HASATTR, args_wam)
            return self.eval_opimpl(call, w_opimpl, args_wam)

        elif wam_func.color == "blue" and wam_func.w_blueval is B.w_setattr:
            self.special_calls[call] = "setattr"
            w_opimpl = self.vm.call_OP(call.loc, OP.w_SETATTR, args_wam)
            return self.eval_opimpl(call, w_opimpl, args_wam)

        else:
            # normal case
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

    def _call_method_blue(
        self, op: ast.Starred, wam_obj: W_MetaArg, methname: str
    ) -> W_MetaArg:
        """
        `wam_obj.methname()`, evaluated eagerly and blue, via the same
        OP.w_CALL_METHOD dynamic-dispatch opcode that `x.method(...)`
        expressions and the `for`-loop desugaring use (see
        eval_expr_CallMethod and astcompile.py:compile_stmt_For).

        We deliberately do NOT use vm.lookup_global(w_T.fqn.join(methname))
        here (unlike spy/vm/struct.py:unwrap_dict): that only works for
        methods that happen to also be registered as plain globals (true of
        compiled-from-.spy methods like dict's, but NOT of interp-level
        @builtin_method-decorated methods like interp_tuple's __fastiter__,
        which live only in the type's own method table). Going through
        OP.w_CALL_METHOD works uniformly for both.
        """
        wam_meth = W_MetaArg.from_w_obj(self.vm, self.vm.wrap(methname))
        w_opimpl = self.vm.call_OP(op.loc, OP.w_CALL_METHOD, [wam_obj, wam_meth])
        return self.eval_opimpl(op, w_opimpl, [wam_obj, wam_meth])

    def _blue_splat_items(self, op: ast.Starred, wam_seq: W_MetaArg) -> list[W_Object]:
        """
        Eagerly drain a blue value through the __fastiter__ protocol -- the
        same one that `for` loops desugar to (see
        astcompile.py:compile_stmt_For) -- and collect every item into a
        plain list. Used to implement `*expr` splats.

        `wam_seq` must be blue: this deliberately does NOT support splatting
        a red value, whose length is not known at compile time (see
        eval_starred_items below for the error raised in that case).
        """
        assert wam_seq.color == "blue"
        w_T = wam_seq.w_static_T
        if w_T.lookup_func(self.vm, "__fastiter__") is None:
            w_Tname = w_T.fqn.human_name(self.vm)
            raise SPyError.simple(
                "W_TypeError",
                f"cannot unpack `{w_Tname}`: it does not support "
                "iteration, so it cannot be splatted with `*`",
                "this is not supported",
                op.loc,
            )
        wam_it = self._call_method_blue(op, wam_seq, "__fastiter__")

        items_w = []
        while True:
            wam_cont = self._call_method_blue(op, wam_it, "__continue_iteration__")
            if not self.vm.unwrap_bool(wam_cont.w_val):
                break
            wam_item = self._call_method_blue(op, wam_it, "__item__")
            items_w.append(wam_item.w_val)
            wam_it = self._call_method_blue(op, wam_it, "__next__")
        return items_w

    def eval_starred_items(self, op: ast.Starred) -> list[W_MetaArg]:
        """
        Evaluate a `*expr` splat and expand it into zero or more items.

        This is currently supported only as an item of a `List` literal (see
        eval_expr_List), for any blue value whose type implements the
        __fastiter__ protocol (the same one `for` loops desugar to) -- this
        includes, but is not limited to, the blue `interp_tuple` type which
        backs variadic blue arguments, i.e. `*m_args` in a `@blue.metafunc`
        definition. Returns one W_MetaArg per element.

        Splatting a *red* value is out of scope for now: the target
        container's static type would need to reflect a variable-length
        unpack, which is a materially bigger feature.
        """
        wam_seq = self.eval_expr(op.value)
        if wam_seq.color != "blue":
            raise SPyError.simple(
                "W_TypeError",
                "cannot splat a red value: `*expr` is currently supported "
                "only for blue values",
                "this is not supported",
                op.value.loc,
            )
        items_w = self._blue_splat_items(op, wam_seq)
        return [W_MetaArg.from_w_obj(self.vm, w_item, loc=op.loc) for w_item in items_w]

    def eval_expr_Starred(self, op: ast.Starred) -> W_MetaArg:
        """
        Generic fallback for a `*expr` splat appearing somewhere that
        doesn't special-case ast.Starred before calling self.eval_expr(...)
        on it (e.g. Call args, today). List/Tuple deliberately pre-check
        `isinstance(item, ast.Starred)` and route to eval_starred_items
        instead of going through here -- see eval_expr_List.
        """
        raise SPyError.simple(
            "W_TypeError",
            "splat expressions (`*expr`) are supported only as items of "
            "a list or tuple literal",
            "not supported here",
            op.loc,
        )

    def eval_expr_List(self, lst: ast.List) -> W_MetaArg:
        # 0. empty lists are special
        if len(lst.items) == 0:
            w_T = SPY.w_EmptyListType
            w_val = SPY.w_empty_list
            return W_MetaArg(self.vm, "red", w_T, w_val, lst.loc)

        # 1. evaluate the individual items (expanding any `*expr` splat into
        # zero or more items) and infer the itemtype
        src_items: list[ast.Expr] = []
        items_wam: list[W_MetaArg] = []
        for item in lst.items:
            if isinstance(item, ast.Starred):
                for wam_item in self.eval_starred_items(item):
                    src_items.append(item)
                    items_wam.append(wam_item)
            else:
                src_items.append(item)
                items_wam.append(self.eval_expr(item))

        # a list made only of splatted, empty interp_tuple(s) is empty too
        if len(items_wam) == 0:
            w_T = SPY.w_EmptyListType
            w_val = SPY.w_empty_list
            return W_MetaArg(self.vm, "red", w_T, w_val, lst.loc)

        w_itemtype = None
        color: Color = "red"  # XXX should be blue?
        for i, wam_item in enumerate(items_wam):
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
            items_wam[i] = wam_item

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

        for item, wam_item in zip(src_items, items_wam):
            w_opimpl = self.vm.call_OP(
                lst.loc, OP.w_CALL, [wam_push, wam_list, wam_item]
            )
            wam_list = self.eval_opimpl(item, w_opimpl, [wam_push, wam_list, wam_item])

        return wam_list

    def eval_expr_Slice(self, op: ast.Slice) -> W_MetaArg:
        w_SliceType = self.vm.lookup_global(FQN("_slice::Slice"))
        assert isinstance(w_SliceType, W_Type)

        wam_T = W_MetaArg.from_w_obj(self.vm, w_SliceType)
        args = [self.eval_expr(arg) for arg in (op.start, op.stop, op.step)]
        w_opimpl = self.vm.call_OP(op.loc, OP.w_CALL, [wam_T] + args)
        wam_slice = self.eval_opimpl(op, w_opimpl, [wam_T] + args)
        return wam_slice

    def eval_expr_Tuple(self, tup: ast.Tuple) -> W_MetaArg:
        # 1. evaluate each item
        items_wam = [self.eval_expr(item) for item in tup.items]
        itemtypes_w = [wam.w_static_T for wam in items_wam]
        colors = [wam.color for wam in items_wam]
        color = maybe_blue(*colors)

        # 2. get the tuple type
        w_TupleType = self.vm.lookup_global(FQN("_tuple::tuple"))
        w_T = self.vm.getitem_w(w_TupleType, *itemtypes_w, loc=tup.loc)
        wam_T = W_MetaArg.from_w_obj(self.vm, w_T)

        # 3. instantiate it
        w_opimpl = self.vm.call_OP(tup.loc, OP.w_CALL, [wam_T] + items_wam)
        wam_tuple = self.eval_opimpl(tup, w_opimpl, [wam_T] + items_wam)
        return wam_tuple

    def eval_expr_Dict(self, dict: ast.Dict) -> W_MetaArg:
        # 0. empty dicts are special
        if len(dict.items) == 0:
            w_T = SPY.w_EmptyDictType
            w_val = SPY.w_empty_dict
            return W_MetaArg(self.vm, "red", w_T, w_val, dict.loc)

        # 1. evaluate type of key, value then infer the whole items type.
        key_value_pair = []
        w_keytype = None
        w_valuetype = None
        key_color: Color = "red"
        value_color: Color = "red"
        for pair in dict.items:
            key = self.eval_expr(pair.key)
            value = self.eval_expr(pair.value)

            # If we have two blue items which happen to be equal, we reuse the same
            # w_opimpl for push() below, with the result of pushing the first item
            # twice, and the second item never. By making it red, we force to create a
            # more generic opimpl. See also the corresponding code in eval_expr_List
            key = key.as_red(self.vm)
            value = value.as_red(self.vm)

            key_value_pair.append((key, value))
            key_color = maybe_blue(key_color, key.color)
            value_color = maybe_blue(value_color, value.color)
            if w_keytype is None:
                # first iteration; key, value type are both None
                # according to dict behavior as pair of key, value
                # set key, value type
                assert w_valuetype is None
                w_keytype = key.w_static_T
                w_valuetype = value.w_static_T
            else:
                # second iteration and so on.
                # compute union type covering both current key, value and new key, value type
                assert w_valuetype is not None
                w_keytype = self.vm.union_type(w_keytype, key.w_static_T)
                w_valuetype = self.vm.union_type(w_valuetype, value.w_static_T)

        assert w_keytype is not None
        assert w_valuetype is not None

        # 2. instantiate a new dict
        w_DictType = self.vm.lookup_global(FQN("_dict::dict"))
        w_T = self.vm.getitem_w(w_DictType, w_keytype, w_valuetype)  # dict[K, V]
        wam_T = W_MetaArg.from_w_obj(self.vm, w_T)

        w_opimpl = self.vm.call_OP(dict.loc, OP.w_CALL, [wam_T])
        wam_dict = self.eval_opimpl(dict, w_opimpl, [wam_T])

        # 3. push items into the dict
        assert isinstance(w_T, W_Type)
        fqn_push = w_T.fqn.join("_push")
        w_push = self.vm.lookup_global(fqn_push)
        wam_push = W_MetaArg.from_w_obj(self.vm, w_push)

        for pair, (wam_key, wam_val) in zip(dict.items, key_value_pair):
            w_opimpl = self.vm.call_OP(
                dict.loc, OP.w_CALL, [wam_push, wam_dict, wam_key, wam_val]
            )
            wam_dict = self.eval_opimpl(
                pair, w_opimpl, [wam_push, wam_dict, wam_key, wam_val]
            )

        return wam_dict


class ASTFrame(AbstractFrame):
    """
    A frame to execute and ASTFunc
    """

    w_func: W_ASTFunc
    funcdef: ast.FuncDef

    def __init__(
        self, vm: "SPyVM", w_func: W_ASTFunc, args_w: Optional[Sequence[W_Object]]
    ) -> None:
        # if w_func was lowered, automatically use the most lowered version
        w_func = w_func.get_most_lowered_version()
        assert isinstance(w_func, W_ASTFunc)
        assert w_func.funcdef.frameinfo.kind == "function"
        assert w_func.funcdef.stage in ("astcompiled", "redshifted", "linearized")
        ns = w_func.compute_inner_ns(args_w or [])
        super().__init__(
            vm, ns, w_func.funcdef.loc, w_func.funcdef.frameinfo, w_func.closure
        )
        self.w_func = w_func
        self.funcdef = w_func.funcdef

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        if self.w_func.stage != "astcompiled":
            extra = f" ({self.w_func.stage})"
        elif self.w_func.color == "blue":
            extra = " (blue)"
        else:
            extra = ""
        return f"<{cls} for `{self.w_func.fqn}`{extra}>"

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
            for stmt in self.funcdef.body.body:
                if isinstance(stmt, ast.ClassDef):
                    self.fwdecl_ClassDef(stmt)

            self.exec_Block(self.funcdef.body)
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
            slot_name = arg.sym.slot_name
            if param.kind == "simple":
                self.declare_local(slot_name, color, param.w_T, arg.loc)

            elif param.kind == "var_positional":
                # XXX: we don't have typed tuples, for now we just use a
                # generic untyped tuple as the type.
                assert i == len(funcdef.args) - 1
                self.declare_local(slot_name, color, SPY.w_interp_tuple, arg.loc)

            else:
                assert False

    def init_arguments(self, args_w: Sequence[W_Object]) -> None:
        """
        Store the arguments in args_w in the appropriate local var
        """
        w_ft = self.w_func.w_functype

        for i, param in enumerate(w_ft.params):
            arg = self.funcdef.args[i]
            slot_name = arg.sym.slot_name
            if param.kind == "simple":
                w_arg = args_w[i]
                self.store_local(slot_name, w_arg)

            elif param.kind == "var_positional":
                assert i == len(self.funcdef.args) - 1
                items_w = args_w[i:]
                w_varargs = W_InterpTuple(list(items_w))
                self.store_local(slot_name, w_varargs)

            else:
                assert False
