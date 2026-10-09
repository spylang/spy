"""
This module implements the low-level internal `_simd` VM module, exposing `SIMD`.
"""

from typing import TYPE_CHECKING, Annotated, Any, Literal

from spy.errors import SPyError
from spy.fqn import FQN
from spy.vm.b import B
from spy.vm.builtin import builtin_classmethod, builtin_method
from spy.vm.function import W_Func
from spy.vm.irtag import IRTag
from spy.vm.object import W_Object, W_Type
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_I32, W_Dynamic
from spy.vm.registry import ModuleRegistry
from spy.vm.struct import W_StructType

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


SIMD = ModuleRegistry("_simd")


# The set of numeric primitives which are legal SIMD lane dtypes.
SIMD_DTYPES = (
    B.w_i8,
    B.w_u8,
    B.w_i32,
    B.w_u32,
    B.w_f32,
    B.w_i64,
    B.w_u64,
    B.w_f64,
)


@SIMD.builtin_type("SimdType")
class W_SimdType(W_Type):
    """
    The *type* of a SIMD vector, e.g. `SIMD[f32, 4]`.
    """

    w_dtype: W_Type
    size: int

    def repr_hints(self) -> list[str]:
        return super().repr_hints() + ["simd"]

    def is_struct(self, vm: "SPyVM") -> bool:
        return False


@SIMD.builtin_type("Simd")
class W_Simd(W_Object):
    """
    A SIMD vector *value*, e.g. an instance of `SIMD[f32, 4]`.
    """

    __spy_storage_category__ = "value"

    w_simdtype: W_SimdType
    lanes_w: list  # list[W_Object], length == w_simdtype.size

    def __init__(self, w_simdtype: W_SimdType, lanes_w: list) -> None:
        assert len(lanes_w) == w_simdtype.size
        self.w_simdtype = w_simdtype
        self.lanes_w = lanes_w

    def spy_get_w_type(self, vm: "SPyVM") -> W_Type:
        return self.w_simdtype

    def spy_key(self, vm: "SPyVM") -> Any:
        t = self.w_simdtype.spy_key(vm)
        lanes = tuple(w_lane.spy_key(vm) for w_lane in self.lanes_w)
        return ("simd", t, lanes)

    def __repr__(self) -> str:
        fqn = self.w_simdtype.fqn
        return f"<spy simd {fqn}({self.lanes_w})>"

    # ===== construction: SIMD[T, N](v0, ..., vN-1) =====

    @builtin_method("__new__", color="blue", kind="metafunc")
    @staticmethod
    def w_NEW(vm: "SPyVM", wam_self: W_MetaArg, *args_wam: W_MetaArg) -> W_OpSpec:
        w_simdtype = wam_self.w_blueval
        assert isinstance(w_simdtype, W_SimdType)
        size = w_simdtype.size
        nargs = len(args_wam)
        t = w_simdtype.fqn.human_name(vm)

        if nargs == size:
            w_make = _get_or_make_simd_make(vm, w_simdtype, "elements")
            return W_OpSpec(w_make, list(args_wam))

        if nargs == 0:
            err = SPyError("W_TypeError", "SIMD requires explicit initialization")
            err.add(
                "error",
                f"use `{t}.zeros()`, `{t}.splat(x)` or pass {size} values",
                wam_self.loc,
            )
            raise err

        err = SPyError("W_TypeError", f"`{t}` expects {size} values, got {nargs}")
        err.add("error", f"this is `{t}`", wam_self.loc)
        raise err

    # ===== constructors which don't take one value per lane =====

    @builtin_classmethod("zeros", color="blue", kind="metafunc")
    @staticmethod
    def w_ZEROS(vm: "SPyVM", wam_self: W_MetaArg) -> W_OpSpec:
        w_simdtype = wam_self.w_blueval
        assert isinstance(w_simdtype, W_SimdType)
        w_make = _get_or_make_simd_make(vm, w_simdtype, "zeros")
        return W_OpSpec(w_make, [])

    @builtin_classmethod("splat", color="blue", kind="metafunc")
    @staticmethod
    def w_SPLAT(vm: "SPyVM", wam_self: W_MetaArg, wam_x: W_MetaArg) -> W_OpSpec:
        w_simdtype = wam_self.w_blueval
        assert isinstance(w_simdtype, W_SimdType)
        w_make = _get_or_make_simd_make(vm, w_simdtype, "splat")
        return W_OpSpec(w_make, [wam_x])

    # ===== conversion from a list or a tuple =====

    @builtin_method("__convert_from__", color="blue", kind="metafunc")
    @staticmethod
    def w_CONVERT_FROM(
        vm: "SPyVM",
        wam_expT: W_MetaArg,
        wam_gotT: W_MetaArg,
        wam_obj: W_MetaArg,
    ) -> W_OpSpec:
        w_simdtype = wam_expT.w_blueval
        w_gotT = wam_gotT.w_blueval
        assert isinstance(w_simdtype, W_SimdType)
        assert isinstance(w_gotT, W_Type)
        w_dtype = w_simdtype.w_dtype
        size = w_simdtype.size

        if vm.is_list_type(w_gotT):
            converter = "from_list"
        elif vm.is_tuple_type(w_gotT) and isinstance(w_gotT, W_StructType):
            converter = "from_tuple"
            nitems = len(list(w_gotT.iterfields_w()))
            if nitems != size:
                t = w_simdtype.fqn.human_name(vm)
                got = w_gotT.fqn.human_name(vm)
                err = SPyError(
                    "W_TypeError", f"`{t}` expects {size} values, got {nitems}"
                )
                err.add("error", f"this is `{got}`", wam_obj.loc)
                raise err
        else:
            return W_OpSpec.NULL

        vm.import_("simd")
        w_converter = vm.lookup_global(FQN(f"simd::{converter}"))
        w_impl = vm.getitem_w(w_converter, w_dtype, vm.wrap(size), w_gotT)
        assert isinstance(w_impl, W_Func)
        return W_OpSpec(w_impl, [wam_obj])

    # ===== lane read: v[i] (red index) -> simd.getitem =====
    @builtin_method("__getitem__", color="blue", kind="metafunc")
    @staticmethod
    def w_GETITEM(vm: "SPyVM", wam_self: W_MetaArg, wam_i: W_MetaArg) -> W_OpSpec:
        w_simdtype = wam_self.w_static_T
        assert isinstance(w_simdtype, W_SimdType)
        w_dtype = w_simdtype.w_dtype
        size = w_simdtype.size

        SIMD_T = Annotated[W_Simd, w_simdtype]
        T = Annotated[W_Object, w_dtype]
        irtag = IRTag("simd.getitem")

        @vm.register_builtin_func(w_simdtype.fqn, "getitem", irtag=irtag)
        def w_simd_getitem(vm: "SPyVM", w_v: SIMD_T, w_i: W_I32) -> T:
            i = vm.unwrap_i32(w_i)
            if not (0 <= i < size):
                raise SPyError("W_PanicError", "SIMD index out of bounds")
            return w_v.lanes_w[i]

        return W_OpSpec(w_simd_getitem, [wam_self, wam_i])

    # ===== lane replace: v._with_lane(i, x) -> new vector =====
    #
    # SIMD values are immutable, so this returns a modified copy.  It is an
    # internal building block (used by `__convert_from__`).
    @builtin_method("_with_lane", color="blue", kind="metafunc")
    @staticmethod
    def w_WITH_LANE(
        vm: "SPyVM", wam_self: W_MetaArg, wam_i: W_MetaArg, wam_x: W_MetaArg
    ) -> W_OpSpec:
        w_simdtype = wam_self.w_static_T
        assert isinstance(w_simdtype, W_SimdType)
        w_dtype = w_simdtype.w_dtype
        size = w_simdtype.size

        SIMD_T = Annotated[W_Simd, w_simdtype]
        T = Annotated[W_Object, w_dtype]
        irtag = IRTag("simd.with_lane")

        @vm.register_builtin_func(w_simdtype.fqn, "with_lane", irtag=irtag)
        def w_simd_with_lane(vm: "SPyVM", w_v: SIMD_T, w_i: W_I32, w_x: T) -> SIMD_T:
            i = vm.unwrap_i32(w_i)
            if not (0 <= i < size):
                raise SPyError("W_PanicError", "SIMD index out of bounds")
            lanes_w = list(w_v.lanes_w)
            lanes_w[i] = w_x
            return W_Simd(w_simdtype, lanes_w)

        return W_OpSpec(w_simd_with_lane, [wam_self, wam_i, wam_x])

    # ===== lane write: v[i] = x, rejected =====

    @builtin_method("__setitem__", color="blue", kind="metafunc")
    @staticmethod
    def w_SETITEM(
        vm: "SPyVM", wam_self: W_MetaArg, wam_i: W_MetaArg, wam_v: W_MetaArg
    ) -> W_OpSpec:
        w_simdtype = wam_self.w_static_T
        assert isinstance(w_simdtype, W_SimdType)
        t = w_simdtype.fqn.human_name(vm)
        err = SPyError("W_TypeError", f"type `{t}` does not support item assignment")
        err.add("error", f"this is `{t}`", wam_self.loc)
        raise err


def _get_or_make_simd_make(
    vm: "SPyVM",
    w_simdtype: W_SimdType,
    kind: Literal["elements", "splat", "zeros"],
) -> "W_BuiltinFunc":  # type: ignore[name-defined]
    """
    Build (once per (W_SimdType, kind)) and register the red lowering builtin
    for a constructor, returning the cached instance on subsequent calls.
    """
    from spy.vm.function import FuncParam, W_BuiltinFunc, W_FuncType

    w_dtype = w_simdtype.w_dtype
    size = w_simdtype.size

    if kind == "splat":
        fqn = w_simdtype.fqn.join("__splat__")
        w_functype = W_FuncType.new([FuncParam(w_dtype, "simple")], w_simdtype)
        irtag = IRTag("simd.splat")

        def w_make_impl(vm: "SPyVM", w_x: W_Object) -> W_Simd:
            return W_Simd(w_simdtype, [w_x] * size)

    elif kind == "zeros":
        fqn = w_simdtype.fqn.join("__zeros__")
        w_functype = W_FuncType.new([], w_simdtype)
        irtag = IRTag("simd.zeros")

        def w_make_impl(vm: "SPyVM") -> W_Simd:  # type: ignore[misc]
            zero = 0.0 if w_dtype in (B.w_f32, B.w_f64) else 0
            lanes_w = [w_dtype.pyclass(zero) for _ in range(size)]  # type: ignore[call-arg]
            return W_Simd(w_simdtype, lanes_w)

    else:
        fqn = w_simdtype.fqn.join("__make__")
        params = [FuncParam(w_dtype, "simple") for _ in range(size)]
        w_functype = W_FuncType.new(params, w_simdtype)
        irtag = IRTag("simd.make")

        def w_make_impl(vm: "SPyVM", *args_w: W_Object) -> W_Simd:  # type: ignore[misc]
            assert len(args_w) == size
            return W_Simd(w_simdtype, list(args_w))

    w_existing = vm.lookup_global_maybe(fqn)
    if w_existing is not None:
        assert isinstance(w_existing, W_BuiltinFunc)
        assert w_existing.w_functype is w_functype
        return w_existing

    w_func = W_BuiltinFunc(w_functype, fqn, w_make_impl)
    vm.add_global(fqn, w_func, irtag=irtag)
    return w_func


@SIMD.builtin_func(color="blue", kind="generic")
def w_SIMD(vm: "SPyVM", w_dtype: W_Type, w_size: W_I32) -> W_Dynamic:
    """
    The `SIMD` *generic* type constructor.

    Validation (blue-time):

      * `size` must be a *positive power of two* (1, 2, 4, 8, ...).
        - non-positive sizes (0, negative) report
          `"SIMD size must be a positive power of two, got <n>"`;
        - positive but non-power-of-two sizes report
          `"SIMD size must be a power of two, got <n>"`.
      * `dtype` must be one of the v1 numeric primitives
        (i8, u8, i32, u32, f32, i64, u64, f64), else
        `"SIMD element type must be a numeric primitive, got `<T>`"`.
    """
    size = int(vm.unwrap_i32(w_size))

    if size <= 0:
        raise SPyError(
            "W_TypeError", f"SIMD size must be a positive power of two, got {size}"
        )
    if size & (size - 1) != 0:
        raise SPyError("W_TypeError", f"SIMD size must be a power of two, got {size}")

    if w_dtype not in SIMD_DTYPES:
        t = w_dtype.fqn.human_name(vm)
        raise SPyError(
            "W_TypeError",
            f"SIMD element type must be a numeric primitive, got `{t}`",
        )

    vm.fqn_human_aliases[FQN("_simd::SIMD")] = FQN("SIMD")
    fqn = FQN("_simd::SIMD").with_qualifiers([w_dtype.fqn, str(size)])

    w_simdtype = W_SimdType.from_pyclass(fqn, W_Simd)
    w_simdtype.w_dtype = w_dtype
    w_simdtype.size = size
    vm.make_fqn_const(w_simdtype)
    return w_simdtype
