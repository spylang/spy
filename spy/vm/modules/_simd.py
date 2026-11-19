"""
This module implements the low-level internal `_simd` VM module, exposing `SIMD`.
"""

from ctypes import c_float as float32
from typing import TYPE_CHECKING, Annotated, Any, Literal

from spy.errors import SPyError
from spy.fqn import FQN
from spy.vm.b import B
from spy.vm.builtin import builtin_classmethod, builtin_method
from spy.vm.function import FuncParam, W_BuiltinFunc, W_Func, W_FuncType
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
    length: int

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
    lanes_w: list  # list[W_Object], length == w_simdtype.length

    def __init__(self, w_simdtype: W_SimdType, lanes_w: list) -> None:
        assert len(lanes_w) == w_simdtype.length
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
        length = w_simdtype.length
        nargs = len(args_wam)
        t = w_simdtype.fqn.human_name(vm)

        if nargs == 0:
            err = SPyError("W_TypeError", "SIMD requires explicit initialization")
            err.add(
                "error",
                f"use `{t}.zeros()`, `{t}.splat(x)` or pass {length} values",
                wam_self.loc,
            )
            raise err

        elif nargs != length:
            err = SPyError("W_TypeError", f"`{t}` expects {length} values, got {nargs}")
            err.add("error", f"this is `{t}`", wam_self.loc)
            raise err

        w_make = vm.lookup_global(w_simdtype.fqn.join("__make__"))
        assert isinstance(w_make, W_Func)
        return W_OpSpec(w_make, list(args_wam))

    # ===== constructors which don't take one value per lane =====

    @builtin_classmethod("zeros", color="blue", kind="metafunc")
    @staticmethod
    def w_ZEROS(vm: "SPyVM", wam_self: W_MetaArg) -> W_OpSpec:
        w_simdtype = wam_self.w_blueval
        assert isinstance(w_simdtype, W_SimdType)
        w_dtype = w_simdtype.w_dtype
        N = w_simdtype.length
        zero = 0.0 if w_dtype in (B.w_f32, B.w_f64) else 0
        lanes_w = [w_dtype.pyclass(zero) for _ in range(N)]  # type: ignore
        return W_OpSpec.const(W_Simd(w_simdtype, lanes_w))

    @builtin_classmethod("splat", color="blue", kind="metafunc")
    @staticmethod
    def w_SPLAT(vm: "SPyVM", wam_self: W_MetaArg, wam_x: W_MetaArg) -> W_OpSpec:
        w_simdtype = wam_self.w_blueval
        assert isinstance(w_simdtype, W_SimdType)
        SIMD_T = Annotated[W_Simd, w_simdtype]
        T = Annotated[W_Object, w_simdtype.w_dtype]

        @vm.register_builtin_func(
            w_simdtype.fqn, "splat", irtag=IRTag("simd.splat"), is_pure=True
        )
        def w_splat(vm: "SPyVM", w_x: T) -> SIMD_T:
            return W_Simd(w_simdtype, [w_x] * w_simdtype.length)

        return W_OpSpec(w_splat, [wam_x])

    @builtin_classmethod("iota", color="blue", kind="metafunc")
    @staticmethod
    def w_IOTA(vm: "SPyVM", wam_self: W_MetaArg, *args_wam: W_MetaArg) -> W_OpSpec:
        """
        `SIMD[T, N].iota(start=0, step=1)` returns the vector whose lane `i`
        is `start + i * step`.

        Integer lanes never wrap around: if a lane falls outside the range of
        `T`, an error is raised, at compile time when `start` and `step` are
        blue and at runtime otherwise.
        """
        w_simdtype = wam_self.w_blueval
        assert isinstance(w_simdtype, W_SimdType)
        w_dtype = w_simdtype.w_dtype
        N = w_simdtype.length
        SIMD_T = Annotated[W_Simd, w_simdtype]
        T = Annotated[W_Object, w_dtype]
        t = w_simdtype.fqn.human_name(vm)
        dtype = w_dtype.fqn.human_name(vm)

        if len(args_wam) > 2:
            err = SPyError(
                "W_TypeError",
                f"`{t}.iota` expects at most 2 arguments (start, step), "
                f"got {len(args_wam)}",
            )
            err.add("error", f"this is `{t}`", wam_self.loc)
            raise err

        args_wam_full = list(args_wam)
        if len(args_wam_full) == 0:
            w_zero = w_dtype.pyclass(0)  # type: ignore
            args_wam_full.append(W_MetaArg.from_w_obj(vm, w_zero, loc=wam_self.loc))
        if len(args_wam_full) == 1:
            w_one = w_dtype.pyclass(1)  # type: ignore
            args_wam_full.append(W_MetaArg.from_w_obj(vm, w_one, loc=wam_self.loc))

        dtype_limits = vm.int_limits(w_dtype)
        blue_int_args = all(
            wam.is_blue() and vm.int_limits(wam.w_static_T) is not None
            for wam in args_wam_full
        )
        if dtype_limits is not None and blue_int_args:
            # all the lanes are known at compile time: check them now and
            # return a constant, so that no check is needed at runtime
            start_i = int(args_wam_full[0].w_blueval.value)  # type: ignore
            step_i = int(args_wam_full[1].w_blueval.value)  # type: ignore
            lo, hi = dtype_limits
            if not (lo <= start_i <= hi and lo <= start_i + (N - 1) * step_i <= hi):
                lane = next(i for i in range(N) if not lo <= start_i + i * step_i <= hi)
                err = SPyError(
                    "W_TypeError",
                    f"`{t}.iota` overflows `{dtype}`: "
                    f"lane {lane} would be {start_i + lane * step_i}",
                )
                err.add("error", f"this is `{t}`", wam_self.loc)
                raise err
            lanes_w = [w_dtype.pyclass(start_i + i * step_i) for i in range(N)]  # type: ignore
            return W_OpSpec.const(W_Simd(w_simdtype, lanes_w))

        if dtype_limits is None:
            # float dtypes: lanes follow C float semantics, no overflow check
            @vm.register_builtin_func(
                w_simdtype.fqn, "iota", irtag=IRTag("simd.iota"), is_pure=True
            )
            def w_iota(vm: "SPyVM", w_start: T, w_step: T) -> SIMD_T:
                start = w_start.value  # type: ignore
                step = w_step.value  # type: ignore
                items: list
                if w_dtype is B.w_f32:
                    # like C
                    items = [
                        float32(start.value + float32(step.value * i).value)
                        for i in range(N)
                    ]
                else:
                    items = [start + step * i for i in range(N)]
                lanes_w = [w_dtype.pyclass(x) for x in items]  # type: ignore
                return W_Simd(w_simdtype, lanes_w)

        else:
            # int dtypes with red arguments: check at runtime that no lane
            # overflows instead of wrapping
            @vm.register_builtin_func(
                w_simdtype.fqn, "iota", irtag=IRTag("simd.iota"), is_pure=True
            )
            def w_iota(vm: "SPyVM", w_start: T, w_step: T) -> SIMD_T:
                start = w_start.value  # type: ignore
                step = w_step.value  # type: ignore
                assert dtype_limits is not None
                lo, hi = dtype_limits
                start_i = int(start)
                step_i = int(step)
                items = []
                for i in range(N):
                    v = start_i + i * step_i
                    if not lo <= v <= hi:
                        raise SPyError(
                            "W_PanicError",
                            f"`{t}.iota` overflows `{dtype}`: lane {i} would be {v}",
                        )
                    items.append(v)
                lanes_w = [w_dtype.pyclass(x) for x in items]  # type: ignore
                return W_Simd(w_simdtype, lanes_w)

        return W_OpSpec(w_iota, args_wam_full)

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
        length = w_simdtype.length

        if vm.is_list_type(w_gotT):
            converter = "from_list"
        elif vm.is_tuple_type(w_gotT) and isinstance(w_gotT, W_StructType):
            converter = "from_tuple"
            nitems = len(list(w_gotT.iterfields_w()))
            if nitems != length:
                t = w_simdtype.fqn.human_name(vm)
                got = w_gotT.fqn.human_name(vm)
                err = SPyError(
                    "W_TypeError", f"`{t}` expects {length} values, got {nitems}"
                )
                err.add("error", f"this is `{got}`", wam_obj.loc)
                raise err
        else:
            return W_OpSpec.NULL

        vm.import_("simd")
        w_converter = vm.lookup_global(FQN(f"simd::{converter}"))
        w_impl = vm.getitem_w(w_converter, w_dtype, vm.wrap(length), w_gotT)
        assert isinstance(w_impl, W_Func)
        if wam_obj.is_blue():
            w_res = vm.fast_call(w_impl, [wam_obj.w_blueval])
            return W_OpSpec.const(w_res)
        return W_OpSpec(w_impl, [wam_obj])

    # ===== lane read: v[i] (red index) -> simd.getitem =====
    @builtin_method("__getitem__", color="blue", kind="metafunc")
    @staticmethod
    def w_GETITEM(vm: "SPyVM", wam_self: W_MetaArg, wam_i: W_MetaArg) -> W_OpSpec:
        w_simdtype = wam_self.w_static_T
        assert isinstance(w_simdtype, W_SimdType)
        w_dtype = w_simdtype.w_dtype
        length = w_simdtype.length

        SIMD_T = Annotated[W_Simd, w_simdtype]
        T = Annotated[W_Object, w_dtype]
        irtag = IRTag("simd.getitem")

        @vm.register_builtin_func(w_simdtype.fqn, "getitem", irtag=irtag)
        def w_simd_getitem(vm: "SPyVM", w_v: SIMD_T, w_i: W_I32) -> T:
            i = vm.unwrap_i32(w_i)
            if not (0 <= i < length):
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
        length = w_simdtype.length

        SIMD_T = Annotated[W_Simd, w_simdtype]
        T = Annotated[W_Object, w_dtype]
        irtag = IRTag("simd.with_lane")

        @vm.register_builtin_func(w_simdtype.fqn, "with_lane", irtag=irtag)
        def w_simd_with_lane(vm: "SPyVM", w_v: SIMD_T, w_i: W_I32, w_x: T) -> SIMD_T:
            i = vm.unwrap_i32(w_i)
            if not (0 <= i < length):
                raise SPyError("W_PanicError", "SIMD index out of bounds")
            lanes_w = list(w_v.lanes_w)
            lanes_w[i] = w_x
            return W_Simd(w_simdtype, lanes_w)

        return W_OpSpec(w_simd_with_lane, [wam_self, wam_i, wam_x])


@SIMD.builtin_func(color="blue", kind="generic")
def w_SIMD(vm: "SPyVM", w_dtype: W_Type, w_length: W_I32) -> W_Dynamic:
    """
    The `SIMD` generic type constructor.

    Validation (blue-time):

      * `length` must be a positive power of two
      * `dtype` must be one of i8, u8, i32, u32, f32, i64, u64, f64
    """
    length = int(vm.unwrap_i32(w_length))

    if length <= 0:
        raise SPyError(
            "W_TypeError", f"SIMD length must be a positive power of two, got {length}"
        )
    if length & (length - 1) != 0:
        raise SPyError(
            "W_TypeError", f"SIMD length must be a power of two, got {length}"
        )

    if w_dtype not in SIMD_DTYPES:
        t = w_dtype.fqn.human_name(vm)
        raise SPyError(
            "W_TypeError",
            f"SIMD element type must be a numeric primitive, got `{t}`",
        )

    vm.fqn_human_aliases[FQN("_simd::SIMD")] = FQN("SIMD")
    fqn = FQN("_simd::SIMD").with_qualifiers([w_dtype.fqn, str(length)])

    w_simdtype = W_SimdType.from_pyclass(fqn, W_Simd)
    w_simdtype.w_dtype = w_dtype
    w_simdtype.length = length
    vm.make_fqn_const(w_simdtype)

    # the applevel signature is this:
    #     def __make__(v1: T, v2: T, ..., vN: T) -> SIMD[T, N]
    #
    # but the interp-level signature uses varargs for convenience, so we must
    # compute w_functype explicitly.  See test_builtin::test_explicit_functype.
    params = [FuncParam(w_dtype, "simple") for _ in range(length)]
    w_functype = W_FuncType.new(params, w_simdtype)

    @vm.register_builtin_func(
        w_simdtype.fqn,
        "__make__",
        irtag=IRTag("simd.make"),
        w_functype=w_functype,
    )
    def w_make(vm: "SPyVM", *args_w: W_Object) -> W_Simd:
        assert len(args_w) == length
        return W_Simd(w_simdtype, list(args_w))

    return w_simdtype
