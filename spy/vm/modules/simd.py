"""
This module implements the low-level internal `_simd` VM module, exposing `SIMD`.
"""

import operator
from typing import TYPE_CHECKING, Annotated, Any

from spy.errors import SPyError
from spy.fqn import FQN
from spy.vm.b import B
from spy.vm.builtin import builtin_method
from spy.vm.irtag import IRTag
from spy.vm.object import W_Object, W_Type
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import (
    W_F32,
    W_F64,
    W_I8,
    W_I32,
    W_I64,
    W_U8,
    W_U32,
    W_U64,
    W_Dynamic,
)
from spy.vm.registry import ModuleRegistry

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


# the mask dtype for a lane dtype.
#
# GCC/Clang `vector_size` comparison yields a *signed* integer vector of the
# same byte-width as the lane, with lanes -1 (true, all-ones) / 0 (false).  So
# the mask dtype is the signed integer of the lane's byte-width:
SIMD_MASK_DTYPE = {
    B.w_i8: B.w_i8,
    B.w_u8: B.w_i8,
    B.w_i32: B.w_i32,
    B.w_u32: B.w_i32,
    B.w_f32: B.w_i32,
    B.w_i64: B.w_i64,
    B.w_u64: B.w_i64,
    B.w_f64: B.w_i64,
}


SIMD_DTYPE_BYTES = {
    B.w_i8: 1,
    B.w_u8: 1,
    B.w_i32: 4,
    B.w_u32: 4,
    B.w_f32: 4,
    B.w_i64: 8,
    B.w_u64: 8,
    B.w_f64: 8,
}

# integer lane dtypes: only these may serve as a select mask.
SIMD_INT_DTYPES = frozenset({B.w_i8, B.w_u8, B.w_i32, B.w_u32, B.w_i64, B.w_u64})

_W_LANE_CTOR = {
    B.w_i8: W_I8,
    B.w_u8: W_U8,
    B.w_i32: W_I32,
    B.w_u32: W_U32,
    B.w_f32: W_F32,
    B.w_i64: W_I64,
    B.w_u64: W_U64,
    B.w_f64: W_F64,
}


@SIMD.builtin_type("SimdType")
class W_SimdType(W_Type):
    """
    The *type* of a SIMD vector, e.g. `SIMD[f32, 4]`.

    A concrete `W_SimdType` instance is created (and cached) by the
    `SIMD` blue generic (see `w_SIMD` below).  Each instance carries its
    lane `dtype` (a primitive `W_Type`) and its `size` (the number of
    lanes), and is defined from the `W_Simd` value pyclass — which is what
    installs `__getitem__` / `__setitem__` / `__new__` into its
    `dict_w`.

    Like `W_StructType` / `W_PtrType`, the *type* lives outside
    `unsafe`; only the memory I/O (`sizeof` and the
    `generic_mem_read`/`generic_mem_write` branch) lives in `unsafe`.
    """

    w_dtype: W_Type
    size: int

    def repr_hints(self) -> list[str]:
        return super().repr_hints() + ["simd"]

    def is_struct(self, vm: "SPyVM") -> bool:
        # SIMD vectors are not structs: ptr[SIMD[...]] loads/stores them
        # *by value* (see W_Ptr.w_GETITEM), they never become a ref[T].
        return False


@SIMD.builtin_type("Simd")
class W_Simd(W_Object):
    """
    A SIMD vector *value*, e.g. an instance of `SIMD[f32, 4]`.

    Interp-level representation: a plain Python list of `size` lane values
    (each a `W_Object` of `w_dtype`).  This is a *value* type: it is
    immutable (only `__getitem__`, no `__setitem__`), compares by value,
    and is passed/returned by value between SPy functions.  Mutation /
    addressing of individual lanes exists only through `ptr[SIMD[...]]`,
    mirroring `struct`.
    """

    __spy_storage_category__ = "value"

    w_simdtype: W_SimdType
    lanes_w: list  # list[W_Object], length == w_simdtype.size

    def __init__(self, w_simdtype: W_SimdType, lanes_w: list) -> None:
        assert len(lanes_w) == w_simdtype.size
        self.w_simdtype = w_simdtype
        self.lanes_w = lanes_w

    def spy_get_w_type(self, vm: "SPyVM") -> W_Type:
        # The app-level type is the concrete W_SimdType (e.g.
        # `_simd::SIMD[f32, 4]`), NOT the `Simd` base type registered above.
        return self.w_simdtype

    def spy_key(self, vm: "SPyVM") -> Any:
        t = self.w_simdtype.spy_key(vm)
        lanes = tuple(w_lane.spy_key(vm) for w_lane in self.lanes_w)
        return ("simd", t, lanes)

    def __repr__(self) -> str:
        fqn = self.w_simdtype.fqn
        return f"<spy simd {fqn}({self.lanes_w})>"

    # ===== construction: SIMD[T, N](...) =====
    #
    # Calling a W_SimdType means "instantiate it".  W_Type.w_CALL dispatches to
    # __new__; here we turn it into a `simd.make` builtin call (compound
    # literal in C).  Two shapes are supported:
    #   * broadcast:   SIMD[T, N](scalar)        -> {scalar, ..., scalar}
    #   * per-element:  SIMD[T, N](v0, ..., vN-1) -> {v0, ..., vN-1}
    #
    # We build the lowering builtin explicitly (like struct's `_create_w_make`)
    # with a fixed-arity W_FuncType, rather than deriving it from a Python
    # signature: per-element make needs exactly `size` params, which we
    # cannot spell as a static Python signature.
    @builtin_method("__new__", color="blue", kind="metafunc")
    @staticmethod
    def w_NEW(vm: "SPyVM", wam_self: W_MetaArg, *args_wam: W_MetaArg) -> W_OpSpec:
        w_simdtype = wam_self.w_blueval
        assert isinstance(w_simdtype, W_SimdType)
        size = w_simdtype.size
        nargs = len(args_wam)

        if nargs == 1:
            # broadcast: SIMD[T, N](scalar)
            w_make = _get_or_make_simd_make(vm, w_simdtype, broadcast=True)
            return W_OpSpec(w_make, [args_wam[0]])

        elif nargs == size:
            # per-element: SIMD[T, N](v0, ..., v_{N-1})
            w_make = _get_or_make_simd_make(vm, w_simdtype, broadcast=False)
            return W_OpSpec(w_make, list(args_wam))

        else:
            # Anything else (e.g. 2 args for a 4-wide vector): not supported in
            # PR1.  Returning NULL yields a clear "cannot call" type error.
            return W_OpSpec.NULL

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

    # ===== lane write: v[i] = x — rejected =====
    #
    # SIMD values are immutable: only __getitem__ is provided.  A bare
    # `v[i] = x` is not supported in PR1 (simd.setitem is postponed to a later
    # PR).  We implement __setitem__ as a metafunc that raises a precise error
    # instead of letting the generic "cannot do `{0}[`{1}`] = ...` message
    # through, so the diagnostic matches the value-semantics contract.
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

    # ===== elementwise arithmetic: simd.binop =====
    #
    # `a + b`, `a - b`, `a * b`, `a / b` (float only) lower to a single
    # `simd.binop` irtag carrying the C operator; the C backend emits
    # `C.BinOp(op, l, r)`.  Each metafunc builds (once per (W_SimdType, op))
    # a red plain builtin with functype `(T, T) -> T` and returns a SIMPLE
    # OpSpec to it, so `typecheck_opspec` rebinds against the live call args.

    @builtin_method("__add__", color="blue", kind="metafunc")
    @staticmethod
    def w_ADD(vm: "SPyVM", wam_self: W_MetaArg, wam_other: W_MetaArg) -> W_OpSpec:
        return _simd_binop_meta(
            vm,
            wam_self,
            wam_other,
            dunder="add",
            c_op="+",
            op_py=operator.add,
        )

    @builtin_method("__sub__", color="blue", kind="metafunc")
    @staticmethod
    def w_SUB(vm: "SPyVM", wam_self: W_MetaArg, wam_other: W_MetaArg) -> W_OpSpec:
        return _simd_binop_meta(
            vm,
            wam_self,
            wam_other,
            dunder="sub",
            c_op="-",
            op_py=operator.sub,
        )

    @builtin_method("__mul__", color="blue", kind="metafunc")
    @staticmethod
    def w_MUL(vm: "SPyVM", wam_self: W_MetaArg, wam_other: W_MetaArg) -> W_OpSpec:
        return _simd_binop_meta(
            vm,
            wam_self,
            wam_other,
            dunder="mul",
            c_op="*",
            op_py=operator.mul,
        )

    @builtin_method("__div__", color="blue", kind="metafunc")
    @staticmethod
    def w_DIV(vm: "SPyVM", wam_self: W_MetaArg, wam_other: W_MetaArg) -> W_OpSpec:
        # `/` is v1 float-only: integer `/` (truncation-vs-floor) is a
        # semantic decision deferred to a follow-up.  Returning NULL yields
        # the standard `cannot do `SIMD[i32,4]` / `SIMD[i32,4]` type error.
        return _simd_binop_meta(
            vm,
            wam_self,
            wam_other,
            dunder="div",
            c_op="/",
            op_py=operator.truediv,
        )

    # ===== elementwise comparison: simd.cmp =====
    #
    # All six comparisons lower to the `simd.cmp` irtag carrying the C
    # operator; the C result is a *signed* integer vector (the mask type, see
    # `get_mask_simdtype`) of the lane's byte-width, with lanes -1 (true) /
    # 0 (false) -- matching the GCC/Clang `vector_size` comparison result.
    # Defining all six explicitly also overrides the scalar `__eq__`/`__ne__`
    # that `W_Type.define._add_eq_ne_maybe` would otherwise auto-generate from
    # `spy_key` (W_Simd is a value type with a spy_key).

    @builtin_method("__eq__", color="blue", kind="metafunc")
    @staticmethod
    def w_EQ(vm: "SPyVM", wam_self: W_MetaArg, wam_other: W_MetaArg) -> W_OpSpec:
        return _simd_cmp_meta(
            vm,
            wam_self,
            wam_other,
            dunder="eq",
            c_op="==",
            cmp_py=operator.eq,
        )

    @builtin_method("__ne__", color="blue", kind="metafunc")
    @staticmethod
    def w_NE(vm: "SPyVM", wam_self: W_MetaArg, wam_other: W_MetaArg) -> W_OpSpec:
        return _simd_cmp_meta(
            vm,
            wam_self,
            wam_other,
            dunder="ne",
            c_op="!=",
            cmp_py=operator.ne,
        )

    @builtin_method("__lt__", color="blue", kind="metafunc")
    @staticmethod
    def w_LT(vm: "SPyVM", wam_self: W_MetaArg, wam_other: W_MetaArg) -> W_OpSpec:
        return _simd_cmp_meta(
            vm,
            wam_self,
            wam_other,
            dunder="lt",
            c_op="<",
            cmp_py=operator.lt,
        )

    @builtin_method("__le__", color="blue", kind="metafunc")
    @staticmethod
    def w_LE(vm: "SPyVM", wam_self: W_MetaArg, wam_other: W_MetaArg) -> W_OpSpec:
        return _simd_cmp_meta(
            vm,
            wam_self,
            wam_other,
            dunder="le",
            c_op="<=",
            cmp_py=operator.le,
        )

    @builtin_method("__gt__", color="blue", kind="metafunc")
    @staticmethod
    def w_GT(vm: "SPyVM", wam_self: W_MetaArg, wam_other: W_MetaArg) -> W_OpSpec:
        return _simd_cmp_meta(
            vm,
            wam_self,
            wam_other,
            dunder="gt",
            c_op=">",
            cmp_py=operator.gt,
        )

    @builtin_method("__ge__", color="blue", kind="metafunc")
    @staticmethod
    def w_GE(vm: "SPyVM", wam_self: W_MetaArg, wam_other: W_MetaArg) -> W_OpSpec:
        return _simd_cmp_meta(
            vm,
            wam_self,
            wam_other,
            dunder="ge",
            c_op=">=",
            cmp_py=operator.ge,
        )

    # ===== mask.select(a, b): simd.select =====
    #
    # `mask.select(a, b)` is a method call.  The default call-method machinery
    # (`default_callmethod`) would route the metafunc through `op_METACALL`,
    # which wraps every operand with `W_MetaArg.from_w_obj` and *loses* the
    # concrete SIMD types (`wam_self.w_static_T` would become `W_MetaArg`).
    # We therefore define `__call_method__` on `W_Simd`: `w_CALL_METHOD`
    # (callop) dispatches it via `fast_metacall`, passing the *real* red
    # MetaArgs, so we can read the mask/operand `W_SimdType`s.
    #
    # We handle "select" (building the per-(mask, operand) `simd.select`
    # builtin) and return `W_OpSpec.NULL` for anything else, which produces
    # the "method `...::meth` does not exist" error.

    @builtin_method("__call_method__", color="blue", kind="metafunc")
    @staticmethod
    def w_CALL_METHOD(
        vm: "SPyVM",
        wam_self: W_MetaArg,
        wam_meth: W_MetaArg,
        *args_wam: W_MetaArg,
    ) -> W_OpSpec:
        if not wam_meth.is_blue():
            return W_OpSpec.NULL
        meth = vm.unwrap_str(wam_meth.w_blueval)
        if meth == "select" and len(args_wam) == 2:
            w_mask_t = wam_self.w_static_T
            w_op_t = args_wam[0].w_static_T
            if (
                isinstance(w_mask_t, W_SimdType)
                and isinstance(w_op_t, W_SimdType)
                and _is_valid_mask(w_mask_t, w_op_t)
            ):
                w_sel = _get_or_make_simd_select(vm, w_mask_t, w_op_t)
                return W_OpSpec(w_sel)
        return W_OpSpec.NULL


def _get_or_make_simd_make(
    vm: "SPyVM", w_simdtype: W_SimdType, *, broadcast: bool
) -> "W_BuiltinFunc":  # type: ignore[name-defined]
    """
    Build (once per (W_SimdType, shape)) and register the red `simd.make`
    lowering builtin, returning the cached instance on subsequent calls.

    This mirrors struct's `W_StructType._create_w_make`: we construct the
    `W_BuiltinFunc` directly with a fixed-arity `W_FuncType` rather than
    deriving the functype from a Python signature (per-element make needs
    exactly `size` params, which cannot be spelled statically).

    The broadcast and per-element lowers share the `simd.make` irtag (the
    C backend dispatches on the tag and inspects `irtag.data['broadcast']`),
    but live at distinct FQNs because they have different arities.
    """
    from spy.vm.function import FuncParam, W_BuiltinFunc, W_FuncType

    w_dtype = w_simdtype.w_dtype
    size = w_simdtype.size

    if broadcast:
        fqn = w_simdtype.fqn.join("__make_broadcast__")
        w_functype = W_FuncType.new([FuncParam(w_dtype, "simple")], w_simdtype)
        irtag = IRTag("simd.make", broadcast=True)

        def w_make_impl(vm: "SPyVM", w_x: W_Object) -> W_Simd:
            return W_Simd(w_simdtype, [w_x] * size)

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
        # Already registered by an earlier call site (or a re-typecheck).
        # W_FuncType is interned, so the functype is the very same object.
        assert isinstance(w_existing, W_BuiltinFunc)
        assert w_existing.w_functype is w_functype
        return w_existing

    w_func = W_BuiltinFunc(w_functype, fqn, w_make_impl)
    vm.add_global(fqn, w_func, irtag=irtag)
    return w_func


# ===== mask type + binop/cmp/select lowering builtins =====


def _lane_py(w_lane: Any, w_dtype: W_Type) -> Any:
    """
    Unwrap a SIMD lane W_Object to a plain Python value for interp arithmetic.
    """
    if w_dtype is B.w_f32:
        return w_lane.value.value
    if w_dtype is B.w_f64:
        return w_lane.value
    return int(w_lane.value)


def get_mask_simdtype(vm: "SPyVM", w_simdtype: W_SimdType) -> W_SimdType:
    """
    The mask `W_SimdType` for a given operand `W_SimdType`: the
    signed-integer SIMD vector of the lane's byte-width and the same size
    (e.g. `SIMD[f32, 4]` -> `SIMD[i32, 4]`).  Built by calling the `SIMD`
    blue generic, so it is interned + registered as a global exactly like a
    user-written `SIMD[i32, 4]` (and emitted as a typedef by the C backend).
    """
    w_mask_dtype = SIMD_MASK_DTYPE[w_simdtype.w_dtype]
    size = int(w_simdtype.size)
    w_mask_simdtype = vm.fast_call(SIMD.w_SIMD, [w_mask_dtype, W_I32(size)])
    assert isinstance(w_mask_simdtype, W_SimdType)
    return w_mask_simdtype


def _is_valid_mask(w_mask_t: W_SimdType, w_op_t: W_SimdType) -> bool:
    """
    A select mask must be an integer SIMD vector of the same size and the
    same lane byte-width as the operand, so the C same-size reinterpret
    casts in the bit-trick blend are valid.
    """
    return (
        w_mask_t.size == w_op_t.size
        and w_mask_t.w_dtype in SIMD_INT_DTYPES
        and SIMD_DTYPE_BYTES[w_mask_t.w_dtype] == SIMD_DTYPE_BYTES[w_op_t.w_dtype]
    )


def _get_or_make_simd_op(
    vm: "SPyVM",
    w_simdtype: W_SimdType,
    *,
    dunder: str,
    c_op: str,
    tag: str,
    w_restype: W_Type,
    w_impl: Any,
) -> "W_BuiltinFunc":  # type: ignore[name-defined]
    """
    Build (once per (W_SimdType, op)) and register the red lowering builtin
    for a binop/cmp, returning the cached instance on subsequent calls.
    Mirrors `_get_or_make_simd_make`: explicit `W_FuncType` (so we can set
    the cmp restype to the mask type), `lookup_global_maybe` caching, a
    distinct FQN per (W_SimdType, op).  The C backend dispatches on `tag`
    and reads `irtag.data['op']`.
    """
    from spy.vm.function import FuncParam, W_BuiltinFunc, W_FuncType

    fqn = w_simdtype.fqn.join(f"__{dunder}__")
    w_functype = W_FuncType.new(
        [FuncParam(w_simdtype, "simple"), FuncParam(w_simdtype, "simple")],
        w_restype,
    )
    irtag = IRTag(tag, op=c_op)

    w_existing = vm.lookup_global_maybe(fqn)
    if w_existing is not None:
        assert isinstance(w_existing, W_BuiltinFunc)
        return w_existing

    w_func = W_BuiltinFunc(w_functype, fqn, w_impl)
    vm.add_global(fqn, w_func, irtag=irtag)
    return w_func


def _get_or_make_simd_select(
    vm: "SPyVM", w_mask_t: W_SimdType, w_op_t: W_SimdType
) -> "W_BuiltinFunc":  # type: ignore[name-defined]
    """
    Build (once per (mask, operand)) and register the red `simd.select`
    lowering builtin.  Functype `(mask, str, T, T) -> T`: the `str` param
    is the method name carried by `w_CALL_METHOD`; it is ignored by the
    impl and skipped by the C lowering, but keeping it lets us return a
    *simple* OpSpec (caching-safe).  The C backend reads the mask/operand C
    types from this functype.  The FQN carries the mask type as a qualifier so
    different masks over the same operand get distinct builtins.
    """
    from spy.vm.function import FuncParam, W_BuiltinFunc, W_FuncType

    fqn = w_op_t.fqn.join("__select__", qualifiers=[w_mask_t.fqn])
    w_functype = W_FuncType.new(
        [
            FuncParam(w_mask_t, "simple"),
            FuncParam(B.w_str, "simple"),
            FuncParam(w_op_t, "simple"),
            FuncParam(w_op_t, "simple"),
        ],
        w_op_t,
    )
    irtag = IRTag("simd.select")

    w_existing = vm.lookup_global_maybe(fqn)
    if w_existing is not None:
        assert isinstance(w_existing, W_BuiltinFunc)
        return w_existing

    def w_impl(
        vm: "SPyVM", w_mask: W_Simd, w_meth: W_Object, w_a: W_Simd, w_b: W_Simd
    ) -> W_Simd:
        # NOTE: interp picks `a[i]`/`b[i]` per `mask[i] != 0`.  This matches
        # the C bit-trick blend `(T)((mask & (M)a) | (~mask & (M)b))` for
        # *canonical* masks (comparison results, lanes 0 / -1).
        # Arbitrary integer masks are accepted at the type level
        # but may diverge between interp and C; use comparison masks for
        # guaranteed cross-backend parity.
        lanes = [
            x if int(m.value) != 0 else y
            for m, x, y in zip(w_mask.lanes_w, w_a.lanes_w, w_b.lanes_w)
        ]
        return W_Simd(w_op_t, lanes)

    w_func = W_BuiltinFunc(w_functype, fqn, w_impl)
    vm.add_global(fqn, w_func, irtag=irtag)
    return w_func


def _simd_binop_meta(
    vm: "SPyVM",
    wam_self: W_MetaArg,
    wam_other: W_MetaArg,
    *,
    dunder: str,
    c_op: str,
    op_py: Any,
) -> W_OpSpec:
    w_simdtype = wam_self.w_static_T
    assert isinstance(w_simdtype, W_SimdType)
    # `/` is v1 float-only; integer `/` is deferred (NULL -> type error).
    if c_op == "/" and not (
        w_simdtype.w_dtype is B.w_f32 or w_simdtype.w_dtype is B.w_f64
    ):
        return W_OpSpec.NULL

    w_dtype = w_simdtype.w_dtype
    lane_ctor = _W_LANE_CTOR[w_dtype]

    def w_impl(vm: "SPyVM", w_a: W_Simd, w_b: W_Simd) -> W_Simd:
        lanes = [
            lane_ctor(op_py(_lane_py(x, w_dtype), _lane_py(y, w_dtype)))
            for x, y in zip(w_a.lanes_w, w_b.lanes_w)
        ]
        return W_Simd(w_simdtype, lanes)

    w_func = _get_or_make_simd_op(
        vm,
        w_simdtype,
        dunder=dunder,
        c_op=c_op,
        tag="simd.binop",
        w_restype=w_simdtype,
        w_impl=w_impl,
    )
    return W_OpSpec(w_func)


def _simd_cmp_meta(
    vm: "SPyVM",
    wam_self: W_MetaArg,
    wam_other: W_MetaArg,
    *,
    dunder: str,
    c_op: str,
    cmp_py: Any,
) -> W_OpSpec:
    w_simdtype = wam_self.w_static_T
    assert isinstance(w_simdtype, W_SimdType)
    w_mask_simdtype = get_mask_simdtype(vm, w_simdtype)
    w_dtype = w_simdtype.w_dtype
    mask_ctor = _W_LANE_CTOR[w_mask_simdtype.w_dtype]

    def w_impl(vm: "SPyVM", w_a: W_Simd, w_b: W_Simd) -> W_Simd:
        lanes = [
            mask_ctor(-1 if cmp_py(_lane_py(x, w_dtype), _lane_py(y, w_dtype)) else 0)
            for x, y in zip(w_a.lanes_w, w_b.lanes_w)
        ]
        return W_Simd(w_mask_simdtype, lanes)

    w_func = _get_or_make_simd_op(
        vm,
        w_simdtype,
        dunder=dunder,
        c_op=c_op,
        tag="simd.cmp",
        w_restype=w_mask_simdtype,
        w_impl=w_impl,
    )
    return W_OpSpec(w_func)


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

    # === validate size ===
    if size <= 0:
        raise SPyError(
            "W_TypeError", f"SIMD size must be a positive power of two, got {size}"
        )
    if size & (size - 1) != 0:
        raise SPyError("W_TypeError", f"SIMD size must be a power of two, got {size}")

    # === validate dtype ===
    if w_dtype not in SIMD_DTYPES:
        t = w_dtype.fqn.human_name(vm)
        raise SPyError(
            "W_TypeError",
            f"SIMD element type must be a numeric primitive, got `{t}`",
        )

    # === register the human alias `_simd::SIMD` -> `SIMD` ===
    #
    # Unlike `list`/`dict`/`tuple`, `SIMD` is NOT re-exported from the builtins
    # prelude (PR1 exposes only the low-level `_simd` module), so it does not
    # get a seeded human alias.  We register one manually so that error
    # messages render `SIMD[f32, 4]` instead of `_simd::SIMD[f32, 4]`.
    # `_resolve_aliases` reattaches the qualifiers, so `_simd::SIMD[f32, 4]`
    # resolves to `SIMD[f32, 4]`.
    vm.fqn_human_aliases[FQN("_simd::SIMD")] = FQN("SIMD")

    # === build the concrete W_SimdType ===
    #
    # The FQN carries both the dtype and the size as qualifiers, so that
    # `SIMD[f32, 4]` human-renders as `SIMD[f32, 4]` and C-mangles to a stable,
    # distinct typedef name `spy__simd$SIMD__f32_4` (one typedef per
    # (dtype, size) pair).  The size is encoded as a bare FQN qualifier, which
    # fqn.c_name renders verbatim.
    fqn = FQN("_simd::SIMD").with_qualifiers([w_dtype.fqn, str(size)])

    # The blue cache memoizes w_SIMD by (dtype spy_key, size spy_key), so
    # repeated `SIMD[f32, 4]` evaluations return the *same* W_SimdType
    # instance.  make_fqn_const then ensures the type is reachable as a global
    # (needed by gc_ptr[SIMD[...]] and by the C backend).
    w_simdtype = W_SimdType.from_pyclass(fqn, W_Simd)
    w_simdtype.w_dtype = w_dtype
    w_simdtype.size = size
    vm.make_fqn_const(w_simdtype)
    return w_simdtype


@SIMD.builtin_func(color="blue", kind="generic")
def w_ptr_load_simd(vm: "SPyVM", w_dtype: W_Type, w_size: W_I32) -> W_Dynamic:
    """
    `ptr_load_simd[T, W](ptr, i)` loads a `SIMD[T, W]` vector of `W`
    consecutive `T` lanes from `ptr` starting at scalar element index `i`.

    `ptr` may be `gc_ptr[T]` or `raw_ptr[T]`.
    """
    from spy.vm.modules.unsafe.mem import generic_mem_read
    from spy.vm.modules.unsafe.misc import sizeof
    from spy.vm.modules.unsafe.ptr import W_Ptr

    w_simdtype = vm.fast_call(SIMD.w_SIMD, [w_dtype, w_size])
    assert isinstance(w_simdtype, W_SimdType)
    w_dtype = w_simdtype.w_dtype

    SIMD_T = Annotated[W_Simd, w_simdtype]
    irtag = IRTag("simd.load")

    @vm.register_builtin_func(w_simdtype.fqn, "ptr_load", irtag=irtag)
    def w_ptr_load_simd_T(vm: "SPyVM", w_ptr: W_Ptr, w_i: W_I32) -> SIMD_T:
        i = vm.unwrap_i32(w_i)
        addr = w_ptr.addr + sizeof(w_dtype) * i
        return generic_mem_read(vm, addr, w_simdtype)

    return w_ptr_load_simd_T


@SIMD.builtin_func(color="blue", kind="metafunc")
def w_ptr_store_simd(
    vm: "SPyVM", wam_ptr: W_MetaArg, wam_i: W_MetaArg, wam_v: W_MetaArg
) -> W_OpSpec:
    """
    `ptr_store_simd(ptr, i, v)` stores the `SIMD[T, W]` vector `v` as `W`
    consecutive `T` lanes into `ptr` starting at scalar element index `i`.

    `T` and `W` are inferred from the static type of `v`.

    `ptr` may be `gc_ptr[T]` or `raw_ptr[T]`.
    """
    from spy.vm.modules.unsafe.mem import generic_mem_write
    from spy.vm.modules.unsafe.misc import sizeof
    from spy.vm.modules.unsafe.ptr import W_Ptr

    w_simdtype = wam_v.w_static_T
    if not isinstance(w_simdtype, W_SimdType):
        got = w_simdtype.fqn.human_name(vm)
        err = SPyError("W_TypeError", "mismatched types")
        err.add("error", f"expected a SIMD value, got `{got}`", loc=wam_v.loc)
        raise err

    w_dtype = w_simdtype.w_dtype

    SIMD_T = Annotated[W_Simd, w_simdtype]
    irtag = IRTag("simd.store")

    @vm.register_builtin_func(w_simdtype.fqn, "ptr_store", irtag=irtag)
    def w_ptr_store_simd_T(vm: "SPyVM", w_ptr: W_Ptr, w_i: W_I32, w_v: SIMD_T) -> None:
        i = vm.unwrap_i32(w_i)
        addr = w_ptr.addr + sizeof(w_dtype) * i
        generic_mem_write(vm, addr, w_simdtype, w_v)

    return W_OpSpec(w_ptr_store_simd_T, [wam_ptr, wam_i, wam_v])
