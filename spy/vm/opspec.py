"""
OpSpec and OpImpl is the central concept to understand of SPy operators work.

Conceptually, the following SPy code:
   c = a + b

is roughly equivalent to:
   arg_a = MetaArg('red', STATIC_TYPE(a))
   arg_b = MetaArg('red', STATIC_TYPE(b))
   opimpl = operator.ADD(arg_a, arg_b)
   c = opimpl(a, b)

I.e., the execution of an operator happens in three-steps:
  1. We call the OPERATOR to determine the OpSpec
  2. The VM convert the OpSpec into an executable OpImpl
  3. We call the OpImpl to determine the final results.

Point (2) is where typechecking happens and can fail.

Note that OPERATORTs don't receive the actual values of operands. Instead,
they receive MetaArgs, which represents "abstract values", of which we know only
the static type.

Then, the OpImpl receives the actual values and compute the result.

This scheme is designed in such a way that the call to OPERATOR() is always
blue and can be optimized away during redshifting.
"""

from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Optional, no_type_check

from spy.analyze.symtable import Color, Symbol
from spy.errors import SPyError
from spy.location import Loc
from spy.vm.b import OPERATOR, B
from spy.vm.builtin import builtin_class_attr, builtin_method, builtin_property
from spy.vm.function import W_Func, W_FuncType
from spy.vm.member import Member
from spy.vm.object import W_Object, W_Type
from spy.vm.primitive import W_Bool
from spy.vm.property import W_Property

if TYPE_CHECKING:
    from spy.vm.primitive import W_Dynamic
    from spy.vm.str import W_Str
    from spy.vm.vm import SPyVM

# if enabled, we assign an unique ID inside W_MetaArg constructuor. It makes it easier
# to distinguish them during debugging sessions.
DEBUG_METAARG = False


@OPERATOR.builtin_type("MetaArg", lazy_definition=True)
class W_MetaArg(W_Object):
    """
    A value which carries some extra information.
    This is a central part of how SPy works.

    In order to preserve the same semantics between interp and compile,
    operation dispatch must be done on STATIC types. The same object can have
    different static types, and thus respond to different operations. For
    example:
        x: MyClass = ...
        y: object = x

    x and y are identical, but have different static types.

    The main job of MetaArgs is to keep track of the color and the static type
    of objects inside the ASTFrame.  As the name suggests, they are then
    passed as arguments to OPERATORs, which can then use the static type to
    dispatch to the proper OpSpec.

    Moreover, they carry around extra information which are used to produce
    better error messages, when needed:
      - loc: the source code location where this object comes from
      - sym: the symbol associated with this objects (if any)

    In interpreter mode, MetaArgs represent concrete values, so they carry an
    actualy object + its static type.

    During redshifting, red MetaArgs are abstract: they carry around only the
    static types.

    Blue MetaArg always have an associated value.

    The naming convention for variables of type W_MetaArg is wam_xxx (for
    Wrapped Argument Meta), because it's "quicker" to pronounce that the more
    correct wma_xxx.
    """

    __spy_storage_category__ = "value"

    color: Color
    w_static_T: Annotated[W_Type, Member("static_type")]
    loc: Loc
    _w_val: Optional[W_Object]
    sym: Optional[Symbol]

    # see DEBUG_METAARG
    debug_counter: ClassVar[int] = 0

    def __init__(
        self,
        vm: "SPyVM",
        color: Color,
        w_static_T: W_Type,
        w_val: Optional[W_Object],
        loc: Loc,
        *,
        sym: Optional[Symbol] = None,
    ) -> None:
        if color == "blue":
            assert w_val is not None
            if w_static_T is B.w_dynamic:
                # "dynamic blue" doesn't make sense: if it's blue, we
                # precisely know its type, and we can eagerly evaluate it.
                # See test_basic::test_eager_blue_eval
                w_static_T = vm.dynamic_type(w_val)
        self.color = color
        self.w_static_T = w_static_T
        self._w_val = w_val
        self.loc = loc
        self.sym = sym
        if DEBUG_METAARG:
            self.debug_id = W_MetaArg.debug_counter
            W_MetaArg.debug_counter += 1

    def spy_key(self, vm: "SPyVM") -> Any:
        """
        Two red opargs are equal if they have the same static types.
        Two blue opargs are equal if they also have the same values.
        """
        t = self.w_static_T.spy_key(vm)
        if self.color == "red":
            return ("MetaArg", "red", t, None)
        else:
            assert self._w_val is not None
            return ("MetaArg", "blue", t, self._w_val.spy_key(vm))

    @builtin_method("__new__")
    @staticmethod
    def w_new(
        vm: "SPyVM", w_color: W_Object, w_static_T: W_Type, w_val: W_Object
    ) -> "W_MetaArg":
        """
        Create a new MetaArg from SPy code:
        - color: 'red' or 'blue'
        - static_type: the static type of the argument
        - val: the value (optional for red MetaArg, required for blue)
        """
        # Check that w_color is a string
        w_T = vm.dynamic_type(w_color)
        if w_T is not B.w_str:
            raise SPyError(
                "W_TypeError",
                f"MetaArg color must be a string, got {w_T.fqn.human_name}",
            )

        color: Color = vm.unwrap_str(w_color)  # type: ignore
        if color not in ("red", "blue"):
            raise SPyError(
                "W_TypeError",
                f"MetaArg color must be 'red' or 'blue', got '{color}'",
            )

        # Convert B.w_None to Python None
        if w_val is B.w_None:
            w_val2 = None
        else:
            w_val2 = w_val

        if color == "blue" and w_val is None:
            raise SPyError("Blue MetaArg requires a value", etype="W_TypeError")

        loc = Loc.here(-2)  # approximate source location
        return W_MetaArg(vm, color, w_static_T, w_val2, loc)

    @classmethod
    def from_w_obj(
        cls,
        vm: "SPyVM",
        w_obj: W_Object,
        *,
        color: Color = "blue",
        loc: Optional[Loc] = None,
    ) -> "W_MetaArg":
        w_T = vm.dynamic_type(w_obj)
        if loc is None:
            loc = Loc.here(-2)
        return W_MetaArg(vm, color, w_T, w_obj, loc)

    def __repr__(self) -> str:
        if self.is_blue():
            extra = f" = {self.w_val}"
        else:
            extra = ""
        t = self.w_static_T.fqn.human_name
        if DEBUG_METAARG:
            extra += f" id={self.debug_id}"
        return f"<W_MetaArg {self.color} {t}{extra}>"

    def is_blue(self) -> bool:
        return self.color == "blue"

    def as_red(self, vm: "SPyVM") -> "W_MetaArg":
        if self.color == "red":
            return self
        return W_MetaArg(
            vm, "red", self.w_static_T, self._w_val, self.loc, sym=self.sym
        )

    @property
    def w_val(self) -> W_Object:
        assert self._w_val is not None, "cannot read w_val from abstract MetaArg"
        return self._w_val

    @property
    def w_blueval(self) -> W_Object:
        assert self.color == "blue"
        assert self._w_val is not None
        return self._w_val

    def blue_ensure(self, vm: "SPyVM", w_expT: W_Type) -> W_Object:
        """
        Ensure that the W_MetaArg is blue and of the expected type.
        Raise SPyError(W_TypeError) if not.
        """
        from spy.vm.modules.operator.convop import CONVERT_maybe

        if self.color != "blue":
            raise SPyError.simple(
                "W_TypeError",
                "expected blue argument",
                "this is red",
                self.loc,
            )

        # check that the blueval has the expected type. If not, we should
        # probably raise a better error, but for now we just fail with
        # AssertionError.
        wam_expT = W_MetaArg.from_w_obj(vm, w_expT)
        w_func = CONVERT_maybe(vm, wam_expT, self)
        assert w_func is None
        assert self.w_val is not None
        return self.w_val

    def blue_unwrap(self, vm: "SPyVM", w_expected_T: W_Type) -> Any:
        """
        Like ensure_blue, but also unwrap.
        """
        w_obj = self.blue_ensure(vm, w_expected_T)
        return vm.unwrap(w_obj)

    def blue_unwrap_str(self, vm: "SPyVM") -> str:
        from spy.vm.b import B

        self.blue_ensure(vm, B.w_str)
        assert self.w_val is not None
        return vm.unwrap_str(self.w_val)

    @builtin_method("__convert_from__", color="blue", kind="metafunc")
    @staticmethod
    def w_CONVERT_FROM(
        vm: "SPyVM", wam_expT: "W_MetaArg", wam_gotT: "W_MetaArg", wam_x: "W_MetaArg"
    ) -> "W_OpSpec":
        w_gotT = wam_gotT.w_blueval
        assert isinstance(w_gotT, W_Type)
        if vm.issubclass(w_gotT, B.w_type):

            @vm.register_builtin_func(W_MetaArg._w.fqn, "from_type")
            def w_from_type(vm: "SPyVM", w_type: W_Type) -> W_MetaArg:
                return W_MetaArg(
                    vm,
                    color="red",
                    w_static_T=w_type,
                    w_val=None,
                    loc=Loc.here(),  # w_from_type
                )

            return W_OpSpec(w_from_type)
        return W_OpSpec.NULL

    @builtin_property("color")
    @staticmethod
    def w_get_color(vm: "SPyVM", w_self: "W_MetaArg") -> "W_Str":
        """
        Applevel property to get the color. We cannot use a simple Member
        because the applevel type (W_Str) doesn't match the interp-level type
        (Color).
        """
        return vm.wrap(w_self.color)

    @builtin_property("blueval")
    @staticmethod
    def w_get_blueval(vm: "SPyVM", w_self: "W_MetaArg") -> "W_Dynamic":
        """
        Applevel property to get the blueval. We cannot use a simple
        Member because we want to do an extra check and raise W_ValueError if
        the color is not blue.
        """
        if w_self.color != "blue":
            raise SPyError("W_ValueError", "oparg is not blue")
        return w_self.w_blueval


@OPERATOR.builtin_type("OpSpec", lazy_definition=True)
class W_OpSpec(W_Object):
    NULL: ClassVar["W_OpSpec"]

    # this is a mess: depending on the presence of some of these attributes
    # the OpSpec can be "NULL", "simple", "complex" and "const". Ideally, we
    # we would like a proper sum type with disjoint attributes, but
    # Python/mypy support for it is very limited and makes things more
    # complicated.
    #
    # The invariants are
    #    - at most one of _w_func and _w_const should be non None
    #    - _args_wam makes sense only if _w_func is non None
    #    - is_direct_call makes sense only if _w_const is None
    _w_func: Optional[W_Func]
    _args_wam: Optional[list[W_MetaArg]]
    _w_const: Optional[W_Object]
    is_direct_call: bool

    # default constructor, for "NULL", "simple" and "complex" cases
    def __init__(
        self,
        w_func: Optional[W_Func],
        args_wam: Optional[list[W_MetaArg]] = None,
        *,
        is_direct_call: bool = False,
    ) -> None:
        self._w_func = w_func
        self._args_wam = args_wam
        self.is_direct_call = is_direct_call
        self._w_const = None

    # constructor for the "const" case
    @staticmethod
    def const(w_obj: W_Object) -> "W_OpSpec":
        w_opspec = W_OpSpec(None, None)
        w_opspec._w_const = w_obj
        return w_opspec

    def __repr__(self) -> str:
        if self._w_func is None:
            return f"<spy OpSpec NULL>"
        elif self._args_wam is None:
            fqn = self._w_func.fqn
            return f"<spy OpSpec {fqn}>"
        elif self._w_const is not None:
            return f"<spy OpSpec const {self._w_const}>"
        else:
            fqn = self._w_func.fqn
            return f"<spy OpSpec {fqn}(...)>"

    def is_null(self) -> bool:
        return self._w_func is None and self._w_const is None

    def is_simple(self) -> bool:
        return self._w_func is not None and self._args_wam is None

    def is_complex(self) -> bool:
        return self._w_func is not None and self._args_wam is not None

    def is_const(self) -> bool:
        return self._w_const is not None

    @property
    def w_functype(self) -> W_FuncType:
        assert self._w_func is not None
        return self._w_func.w_functype

    # ======== app-level interface ========

    @builtin_method("__new__", color="blue", kind="metafunc")
    @staticmethod
    def w_NEW(vm: "SPyVM", wam_cls: W_MetaArg, *args_wam: W_MetaArg) -> "W_OpSpec":
        """
        Operator for creating OpSpec instances with different argument counts.
        - OpSpec(func) -> Simple OpSpec
        - OpSpec(func, args) -> OpSpec with pre-filled arguments
        """
        from spy.vm.function import W_Func
        from spy.vm.modules.__spy__.interp_list import W_MetaArgInterpList

        w_T = wam_cls.w_blueval
        assert isinstance(w_T, W_Type)

        if len(args_wam) == 1:
            # Simple case: OpSpec(func)
            @vm.register_builtin_func(w_T.fqn, "new1")
            def w_new1(vm: "SPyVM", w_cls: W_Type, w_func: W_Func) -> W_OpSpec:
                return W_OpSpec(w_func)

            return W_OpSpec(w_new1)

        elif len(args_wam) == 2:
            # OpSpec(func, args) case
            @vm.register_builtin_func(w_T.fqn, "new2")
            def w_new2(
                vm: "SPyVM", w_cls: W_Type, w_func: W_Func, w_args: W_MetaArgInterpList
            ) -> W_OpSpec:
                # Convert from applevel w_args into interp-level args_w
                args_w = w_args.items_w[:]
                return W_OpSpec(w_func, args_w)

            return W_OpSpec(w_new2)
        else:
            return W_OpSpec.NULL


# make W_OpSpec.NULL available also at applevel, thanks to builtin_class_attr
W_OpSpec.NULL = builtin_class_attr("NULL", W_OpSpec(None))  # type: ignore
