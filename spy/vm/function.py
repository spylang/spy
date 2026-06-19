from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterator,
    Literal,
    Optional,
    Self,
    Sequence,
)

from spy import ast
from spy.ast import Color, FuncKind, FuncParamKind
from spy.errors import SPyError
from spy.fqn import FQN
from spy.location import Loc
from spy.vm.object import W_Object, W_Type, builtin_method

if TYPE_CHECKING:
    from spy.vm.opspec import W_MetaArg, W_OpSpec
    from spy.vm.vm import SPyVM

# =========== Closures ========
#
# - Each frame has a .locals which maps varname -> LocalVar
# - When creating a closure, we capture the .locals of all the outer frames
#
# These types are defined here because we need CLOSURE in the definition of W_ASTFunc,
# but they are manipulated by ASTFrame.


@dataclass
class LocalVar:
    varname: str
    decl_loc: Loc
    color: Color
    w_T: W_Type
    w_val: Optional[W_Object] = None


CLOSURE = tuple[dict[str, LocalVar], ...]
# ========= /Closures =========


@dataclass(frozen=True, eq=True)
class FuncParam:
    """
    Represent a single param of a function.

    Loosely modeled against inspect.Parameter.
    """

    w_T: W_Type
    kind: FuncParamKind

    def get_fqn(self) -> FQN:
        if self.kind == "simple":
            return self.w_T.fqn
        else:
            return FQN("builtins").join("__varargs__", [self.w_T.fqn])


# ==== W_FuncType cache ====
#
# W_Type (and thus W_FuncType) is a reference type and compare by
# identity. Because of that, it's important that FuncTypes are unique inside a
# VM: you should never have two separate FuncTypes with the same color, kind,
# paramlist and restype. To solve that, we keep FuncTypes in a cache and make
# sure to reuse them when needed.
#
# ---- EXT modules hack ----
#
# In theory, the FQN should encode all the needed info to uniquely identify a
# FuncType and could be used as a dict key. However, the test suites contains
# a lot of "ext" modules and "W_MyClass" types: each of them is unique
# per-test (and thus per VM), but their FQNs clashes between runs. The
# workaround is to include FuncParams and w_restype in the dict key, so that
# FuncTypes created by different EXT modules are keyp separated.
#
# This is a hack. The ideal solution would be to have the cache *on the VM*,
# but this would greatly complicate the code, because now ModuleRegistry
# happily creates prebuilt W_BuiltinFunc and W_Type which are shared among
# different VMs.
#
_KEY = tuple[FQN, tuple[FuncParam, ...], W_Type]
_CACHE: dict[_KEY, "W_FuncType"] = {}


@dataclass(repr=False, eq=False)
class W_FuncType(W_Type):
    color: Color
    kind: FuncKind
    params: list[FuncParam]
    w_restype: W_Type

    @staticmethod
    def new(
        params: list[FuncParam],
        w_restype: W_Type,
        *,
        color: Color = "red",
        kind: FuncKind = "plain",
    ) -> "W_FuncType":
        # build an artificial FQN for the functype.
        # E.g. for 'def(i32, i32) -> bool', the FQN looks like this:
        #    builtins::def[i32, i32, bool]
        qualifiers = [p.get_fqn() for p in params] + [w_restype.fqn]
        if color == "red" and kind == "plain":
            t = "def"
        elif color == "blue" and kind == "plain":
            t = "blue.def"
        elif color == "blue" and kind == "generic":
            t = "blue.generic.def"
        elif color == "blue" and kind == "metafunc":
            t = "blue.metafunc.def"
        else:
            assert False
        fqn = FQN("builtins").join(t, qualifiers)

        # see the long comment above to understand why we use this key.  Try
        # to use "key = fqn" and see how tests/compiler/operator/*.py fail
        key = (fqn, tuple(params), w_restype)
        if key in _CACHE:
            return _CACHE[key]

        w_functype = W_FuncType.from_pyclass(fqn, W_Func)
        w_functype.params = params
        w_functype.w_restype = w_restype
        w_functype.color = color
        w_functype.kind = kind

        # print(fqn.debug_human_name)
        _CACHE[key] = w_functype
        return w_functype

    @classmethod
    def parse(cls, s: str) -> "W_FuncType":
        """
        Quick & dirty function to parse function types.

        It's meant to be used in tests, it's not robust at all, especially in
        case of wrong inputs.
        """
        from spy.vm.b import TYPES, B

        def parse_type(s: str) -> Any:
            attr = f"w_{s}"
            if hasattr(B, attr):
                return getattr(B, attr)
            assert False, f"Cannot find type {s}"

        args, res = map(str.strip, s.split("->"))
        assert args.startswith("def(")
        assert args.endswith(")")
        params = []
        arglist = args[4:-1].split(",")
        for argtype in arglist:
            if argtype == "":
                continue
            w_T = parse_type(argtype.strip())
            params.append(FuncParam(w_T, "simple"))
        #
        w_restype = parse_type(res)
        if w_restype is B.w_None:
            # special case None and allow to use it as a type even if it's not
            w_restype = TYPES.w_NoneType
        return cls.new(params, w_restype)

    @property
    def has_varargs(self) -> bool:
        return bool(self.params) and self.params[-1].kind == "var_positional"

    @property
    def arity(self) -> int:
        """
        Return the *minimum* number of arguments expected by the function.
        In case of varargs, it's the number of non-varargs paramenters.
        """
        if self.has_varargs:
            return len(self.params) - 1
        else:
            return len(self.params)

    def is_argcount_ok(self, n: int) -> bool:
        if self.has_varargs:
            return n >= self.arity
        else:
            return n == self.arity

    def all_params(self) -> Iterator[FuncParam]:
        """
        Iterate over all params. Go to infinity in case of varargs
        """
        if self.has_varargs:
            for param in self.params[:-1]:
                yield param
            last_param = self.params[-1]
            while True:
                yield last_param
        else:
            for param in self.params:
                yield param


# we cannot use @builtin_type because of circular import issues. Let's build
# the app-level type manually
W_FuncType._w = W_Type.declare(FQN("builtins::functype"))


class W_Func(W_Object):
    w_functype: W_FuncType
    fqn: FQN
    def_loc: Loc
    w_origin: Optional["W_Object"]

    @property
    def color(self) -> Color:
        """
        Just a shortcut
        """
        return self.w_functype.color

    def is_pure(self) -> bool:
        """
        The result of pure functions depend only on their argument,
        without side effects.

        This means that if we call a red pure function with blue arguments,
        the result can be blue.

        Maybe the proper thing to do is to introduce a new color and store
        this info on the w_functype.
        """
        # this is a hack, but good enough to constant-fold arithmetic ops and other
        # selected ops.
        is_op = self.fqn.modname == "operator" and self.fqn.symbol_name != "raise"
        if isinstance(self, W_BuiltinFunc) and self._is_pure:
            return True
        return is_op or self.fqn in self._pure_fqns

    _pure_fqns = {
        FQN("builtins::type::__new__"),
        FQN("_str::methods::__add__"),
        FQN("_str::methods::__mul__"),
        FQN("_str::methods::__getitem__"),
        FQN("_str::methods::__len__"),
        FQN("_str::methods::__repr__"),
        FQN("_str::methods::replace"),
    }

    def compute_inner_ns(self, args_w: Sequence[W_Object]) -> FQN:
        """
        Try to generate a meaningful namespace for blue functions. The
        idea is that if a blue func takes type parameters, we want to include
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
        quals = [w_arg.fqn for w_arg in args_w if isinstance(w_arg, W_Type)]
        return self.fqn.with_qualifiers(quals)

    def spy_get_w_type(self, vm: "SPyVM") -> W_Type:
        return self.w_functype

    def raw_call(self, vm: "SPyVM", args_w: Sequence[W_Object]) -> W_Object:
        """
        Call the function.

        This is the simplest calling convention, and it's at the base to
        everything else. Arguments can be passed ONLY positionally, and they
        must be of the correct type, no conversions are allowed here.

        Also, raw_call bypasses the blue cache.

        You should never call this directly. Use vm.call or vm.fast_call.
        """
        raise NotImplementedError

    # ======== applevel interface ========

    # NOTE: we cannot use applevel '__call__' or '__getitem__' here, for
    # bootstrapping reason.
    # These operators are special cased by
    # callop.w_CALL and itemop.w_GETITEM, depending on whether w_functype.kind
    # is 'plain' or 'generic'.
    @staticmethod
    def op_CALL(
        vm: "SPyVM", wam_func: "W_MetaArg", wam_funcargs: "W_MetaArg"
    ) -> "W_OpSpec":
        """
        Return an OpSpec which directly calls this function.
        """
        from spy.vm.opspec import W_OpSpec

        w_func = wam_func.w_blueval
        assert isinstance(w_func, W_Func)
        assert w_func.w_functype.kind != "metafunc"

        w_funcargs = wam_funcargs.w_blueval
        assert isinstance(w_funcargs, W_FuncArgs)

        if isinstance(w_func, W_ASTFunc):
            args_wam = w_func._bind_args(vm, w_funcargs)
        else:
            if w_funcargs.kwargs_wam:
                err = SPyError(
                    "W_TypeError", "keyword arguments not supported for this function"
                )
                err.add("error", "keyword arguments not supported", wam_func.loc)
                raise err
            args_wam = w_funcargs.to_list()
        return W_OpSpec(w_func, args_wam, is_direct_call=True)

    @staticmethod
    def op_METACALL(
        vm: "SPyVM", wam_func: "W_MetaArg", wam_funcargs: "W_MetaArg"
    ) -> "W_OpSpec":
        """
        Call this function and use the return value as the OpSpec.
        Keyword arguments are not supported for metafuncs.
        """
        from spy.vm.opspec import W_MetaArg, W_OpSpec
        from spy.vm.typechecker import typecheck_opspec

        w_func = wam_func.w_blueval
        assert isinstance(w_func, W_Func)
        assert w_func.w_functype.kind == "metafunc"

        w_funcargs = wam_funcargs.w_blueval
        assert isinstance(w_funcargs, W_FuncArgs)

        if w_funcargs.kwargs_wam:
            err = SPyError(
                "W_TypeError", "keyword arguments not supported for this function"
            )
            err.add("error", "keyword arguments not supported", wam_func.loc)
            raise err

        # Now we want to call the metafunc to get the opspec to return.  Note
        # that we cannot just vm.fast_call() it, because we don't know whether
        # the metafunc has the right signature. Instead, we do a full
        # OpSpec/typecheck/OpImpl dance, to raise proper TypeErrors if needed.
        # This is a bit of code duplication with callop.w_CALL, but too bad.
        #
        # Metafuncs receive their arguments as MetaArg-typed values, so each
        # call-site wam is wrapped inside another W_MetaArg of type operator::MetaArg.
        args_wam = w_funcargs.to_list()
        meta_args_wam = [W_MetaArg.from_w_obj(vm, wam) for wam in args_wam]
        w_meta_opspec = W_OpSpec(w_func, meta_args_wam)
        w_meta_opimpl = typecheck_opspec(
            vm,
            w_meta_opspec,
            meta_args_wam,
            dispatch="single",
            errmsg="cannot call objects of type `{0}`",
        )
        w_opspec = w_meta_opimpl._execute(vm, meta_args_wam)

        if not isinstance(w_opspec, W_OpSpec):
            w_T = vm.dynamic_type(w_opspec)
            got = w_T.fqn.human_name(vm)
            msg = (
                f"wrong metafunc return type: expected `operator::OpSpec`, got `{got}`"
            )
            err = SPyError("W_TypeError", msg)
            err.add("error", "this is a metafunc", wam_func.loc)
            err.add("note", "metafunc defined here", w_func.def_loc)
            raise err

        # if we return a simple opspec, it will be called with arguments
        # [wam_func, *meta_args_wam]. But what we want is to call it with just
        # *meta_args_wam. This is the equivalent of passing "list(args_wam)" in
        # op_CALL.
        if w_opspec.is_simple():
            w_opspec._args_wam = args_wam

        return w_opspec


class W_FuncArgs(W_Object):
    """
    Encapsulates the payload of a function call: positional args and keyword
    args in source order. Passed as a single W_MetaArg through the call_OP
    machinery. Unpacked by w_CALL / _bind_args before typechecking.
    """

    args_wam: list["W_MetaArg"]
    kwargs_wam: list[tuple[str, "W_MetaArg"]]  # source order

    def __init__(
        self,
        args_wam: list["W_MetaArg"],
        kwargs_wam: list[tuple[str, "W_MetaArg"]],
    ) -> None:
        self.args_wam = args_wam
        self.kwargs_wam = kwargs_wam

    @classmethod
    def from_args(cls, *args_wam: "W_MetaArg") -> "W_FuncArgs":
        return cls(list(args_wam), [])

    def to_list(self) -> list["W_MetaArg"]:
        return self.args_wam + [wam for _, wam in self.kwargs_wam]

    def spy_key(self, vm: "SPyVM") -> Any:
        args_keys = tuple(wam.spy_key(vm) for wam in self.args_wam)
        kwargs_keys = tuple((name, wam.spy_key(vm)) for name, wam in self.kwargs_wam)
        return ("W_FuncArgs", args_keys, kwargs_keys)


# W_FuncArgs is internal and never visible at the SPy level, but needs a
# registered type so vm.dynamic_type() works when wrapping it in a W_MetaArg.
W_FuncArgs._w = W_Type.declare(FQN("builtins::funcargs"))


# =========== W_ASTFunc and compilation stages ========
#
# W_ASTFunc start at the "source" stage. The various compilation passes create new
# versions of the function. Once a function has been lowered it becomes "invalid", and
# we set the `w_replaced_by` field.

LoweringStage = Literal["source", "redshift_in_progress", "redshift", "linearize"]


class W_ASTFunc(W_Func):
    funcdef: ast.FuncDef
    closure: CLOSURE
    defaults_w: list[W_Object]

    # types of local variables: present only after redshifting
    locals_types_w: Optional[dict[str, W_Type]]

    # if the function has been lowered, this contains the NEW function, and the current
    # one becomes invalid
    lowering_stage: LoweringStage
    w_replaced_by: Optional["W_ASTFunc"]

    # set by the @force_inline decorator
    is_force_inline: bool

    def __init__(
        self,
        w_functype: W_FuncType,
        fqn: FQN,
        funcdef: ast.FuncDef,
        closure: CLOSURE,
        defaults_w: list[W_Object],
        *,
        lowering_stage: LoweringStage,
        locals_types_w: Optional[dict[str, W_Type]] = None,
        is_force_inline: bool = False,
    ) -> None:
        self.w_functype = w_functype
        self.fqn = fqn
        self.def_loc = funcdef.prototype_loc
        self.funcdef = funcdef
        self.closure = closure
        self.defaults_w = defaults_w
        self.locals_types_w = locals_types_w
        self.lowering_stage = lowering_stage
        self.w_replaced_by = None
        self.is_force_inline = is_force_inline
        self.w_origin = None

        # sanity check
        if lowering_stage in ("source", "redshift_in_progress"):
            assert self.locals_types_w is None
        else:
            assert self.locals_types_w is not None

    @property
    def is_valid(self) -> bool:
        """
        A function is valid if it has not been replaced by something else.
        """
        return self.w_replaced_by is None

    def replace_with(self, w_func: "W_ASTFunc") -> None:
        assert self.fqn == w_func.fqn
        assert self.w_replaced_by is None
        self.w_replaced_by = w_func

    def get_most_lowered_version(self) -> "W_ASTFunc":
        w_func = self
        while w_func.w_replaced_by is not None:
            w_func = w_func.w_replaced_by
        return w_func

    def __repr__(self) -> str:
        extras = []
        if self.color == "blue":
            extras.append("blue")
        stage = self.lowering_stage
        if stage not in ("source", "redshift_in_progress"):
            extras.append(stage)
        if not self.is_valid:
            extras.append("invalid")

        if extras:
            extra = " (" + ", ".join(extras) + ")"
        else:
            extra = ""
        return f"<spy function '{self.fqn}'{extra}>"

    def raw_call(self, vm: "SPyVM", args_w: Sequence[W_Object]) -> W_Object:
        from spy.vm.astframe import ASTFrame

        frame = ASTFrame(vm, self, args_w)
        return frame.run(args_w)

    def _bind_args(self, vm: "SPyVM", w_funcargs: "W_FuncArgs") -> list["W_MetaArg"]:
        """
        Resolve W_FuncArgs into a fully positional list of W_MetaArg in param
        order, matching keyword args to params by name and filling defaults.
        """
        from spy.vm.opspec import W_MetaArg

        got_posargs_wam = list(w_funcargs.args_wam)
        got_kwargs_wam: dict[str, W_MetaArg] = dict(w_funcargs.kwargs_wam)

        # check for positional args that are also provided as kwargs
        for i, func_arg in enumerate(self.funcdef.args[: len(got_posargs_wam)]):
            if func_arg.name in got_kwargs_wam:
                func_name = self.funcdef.name
                err = SPyError(
                    "W_TypeError",
                    f"{func_name}() got multiple values for argument `{func_arg.name}`",
                )
                err.add("error", "multiple values for argument", func_arg.loc)
                raise err

        defaults_wam: dict[str, W_MetaArg] = {}
        n_default_w = len(self.defaults_w)
        if n_default_w > 0:
            param_names = [arg.name for arg in self.funcdef.args]
            params_with_defaults = param_names[-n_default_w:]
            default_locs = [d.loc for d in self.funcdef.defaults]
            for w_default, loc, param_name in zip(
                self.defaults_w, default_locs, params_with_defaults
            ):
                wam = W_MetaArg.from_w_obj(vm, w_default, loc=loc)
                defaults_wam[param_name] = wam

        args_wam = got_posargs_wam.copy()
        remaining_args = self.funcdef.args[len(got_posargs_wam) :]

        for func_arg in remaining_args:
            param_name = func_arg.name
            if param_name in got_kwargs_wam:
                args_wam.append(got_kwargs_wam.pop(param_name))
            elif param_name in defaults_wam:
                args_wam.append(defaults_wam.pop(param_name))
            else:
                func_name = self.funcdef.name
                err = SPyError(
                    "W_TypeError",
                    f"{func_name}() missing required argument `{param_name}`",
                )
                err.add("error", "missing required argument", func_arg.loc)
                raise err

        if got_kwargs_wam:
            unused = ", ".join(f"`{k}`" for k in got_kwargs_wam)
            err = SPyError("W_TypeError", f"unexpected keyword arguments: {unused}")
            err.add(
                "error",
                "unexpected keyword arguments",
                next(iter(got_kwargs_wam.values())).loc,
            )
            raise err

        return args_wam


class W_BuiltinFunc(W_Func):
    """
    Builtin functions are implemented by calling an interp-level function
    (written in Python).
    """

    pyfunc: Callable

    def __init__(
        self,
        w_functype: W_FuncType,
        fqn: FQN,
        pyfunc: Callable,
        *,
        is_pure: bool = False,
    ) -> None:
        self.w_functype = w_functype
        self.fqn = fqn
        self.def_loc = Loc.from_pyfunc(pyfunc)
        # _pyfunc should NEVER be called directly, because it bypasses the
        # bluecache
        self._pyfunc = pyfunc
        self._is_pure = is_pure
        self.w_origin = None

    def __repr__(self) -> str:
        return f"<spy function '{self.fqn}' (builtin)>"

    def raw_call(self, vm: "SPyVM", args_w: Sequence[W_Object]) -> W_Object:
        from spy.vm.b import TYPES, B

        w_res = self._pyfunc(vm, *args_w)
        if w_res is None and self.w_functype.w_restype is TYPES.w_NoneType:
            return vm.wrap(None)
        return w_res
