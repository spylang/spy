"""
This module implements the low-level internal `_simd` VM module, exposing `SIMD`.
"""

from typing import TYPE_CHECKING, Annotated, Any

from spy.errors import SPyError
from spy.fqn import FQN
from spy.vm.b import B
from spy.vm.builtin import builtin_method
from spy.vm.irtag import IRTag
from spy.vm.object import W_Object, W_Type
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_I32, W_Dynamic
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

        def w_make_impl(vm: "SPyVM", *args_w: W_Object) -> W_Simd:
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
