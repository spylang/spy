"""
Pointer type casting and alignment casting for the unsafe module.

Provides:
- cast[DstItemT](ptr): changes item type, preserves address and alignment
- align_cast[N](ptr): changes alignment tag, preserves address and item type
"""

from typing import TYPE_CHECKING, Annotated

from spy.errors import SPyError
from spy.vm.irtag import IRTag
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_I32, W_Dynamic
from spy.vm.w import W_Type

from . import UNSAFE
from .misc import sizeof
from .ptr import W_Ptr, W_PtrType, w_gc_ptr, w_raw_ptr

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


def _check_ptr_static(vm: "SPyVM", wam_ptr: W_MetaArg, opname: str) -> W_PtrType:
    """
    Validate that wam_ptr is statically typed as ptr[T] (any memkind, any T).
    Mirrors unsafe/mem.py::_check_ptr.
    """
    w_T = wam_ptr.w_static_T
    if isinstance(w_T, W_PtrType):
        return w_T
    t = w_T.fqn.human_name(vm)
    err = SPyError("W_TypeError", "mismatched types")
    err.add("error", f"{opname}: expected ptr[T], got `{t}`", loc=wam_ptr.loc)
    raise err


def _same_memkind_ptrtype(
    vm: "SPyVM", w_srcT: W_PtrType, w_itemT: W_Type, alignment: int
) -> W_PtrType:
    """
    raw_ptr[w_itemT, alignment] or gc_ptr[w_itemT, alignment], matching the
    memkind of w_srcT.
    """
    w_ctor = w_raw_ptr if w_srcT.memkind == "raw" else w_gc_ptr
    w_dstT = vm.fast_call(w_ctor, [w_itemT, vm.wrap(alignment)])
    assert isinstance(w_dstT, W_PtrType)
    return w_dstT


# =============================================================================
# cast[DstItemT](ptr)
# =============================================================================


@UNSAFE.builtin_func(color="blue", kind="generic")
def w_cast(vm: "SPyVM", w_DstItemT: W_Type) -> W_Dynamic:
    """
    cast[DstItemT] -> a metafunc, blue-cached per DstItemT.

    Calling the metafunc with a ptr produces:
        raw_ptr[DstItemT, N] or gc_ptr[DstItemT, N]
    where N is the SOURCE ptr's alignment (preserved) and the memkind also
    matches the source. The length is recomputed from the byte size, with
    truncation. This operation is always safe and has zero runtime overhead.
    """
    ns = UNSAFE.w_cast.compute_inner_ns([w_DstItemT])

    @vm.register_builtin_func(ns, "impl", color="blue", kind="metafunc")
    def w_cast_dispatch(vm: "SPyVM", wam_ptr: W_MetaArg) -> W_OpSpec:
        w_srcT = _check_ptr_static(vm, wam_ptr, "cast")
        w_dstT = _same_memkind_ptrtype(vm, w_srcT, w_DstItemT, w_srcT.alignment)

        src_size = sizeof(w_srcT.w_itemT)
        dst_size = sizeof(w_DstItemT)

        SRC = Annotated[W_Ptr, w_srcT]
        DST = Annotated[W_Ptr, w_dstT]
        irtag = IRTag("unsafe.cast")

        @vm.register_builtin_func(w_srcT.fqn, "cast", [w_DstItemT.fqn], irtag=irtag)
        def w_cast_impl(vm: "SPyVM", w_ptr: SRC) -> DST:
            new_length = (w_ptr.length * src_size) // dst_size
            return W_Ptr(w_dstT, w_ptr.addr, new_length)  # type: ignore

        return W_OpSpec(w_cast_impl, [wam_ptr])

    return w_cast_dispatch


# =============================================================================
# align_cast[N](ptr)
# =============================================================================


@UNSAFE.builtin_func(color="blue", kind="generic")
def w_align_cast(vm: "SPyVM", w_N: W_I32) -> W_Dynamic:
    """
    align_cast[N] -> a metafunc, blue-cached per N.

    Calling the metafunc with a ptr produces raw_ptr[T, N]/gc_ptr[T, N]
    (same memkind and item type as the source, new alignment N):

    - Weakening (N <= old_alignment): free conversion, always safe. Note
      this is also handled implicitly by W_CONVERT_TO for plain assignment;
    - Strengthening (N > old_alignment): asserts addr % N == 0 in DEBUG
      mode (both interp and C); trusts the claim in RELEASE mode (C only;
      the interpreter always checks).
    """
    N = vm.unwrap_i32(w_N)
    ns = UNSAFE.w_align_cast.fqn.with_qualifiers([str(N)])

    @vm.register_builtin_func(ns, "impl", color="blue", kind="metafunc")
    def w_align_cast_dispatch(vm: "SPyVM", wam_ptr: W_MetaArg) -> W_OpSpec:
        w_srcT = _check_ptr_static(vm, wam_ptr, "align_cast")
        old_alignment = w_srcT.alignment
        w_dstT = _same_memkind_ptrtype(vm, w_srcT, w_srcT.w_itemT, N)

        SRC = Annotated[W_Ptr, w_srcT]
        DST = Annotated[W_Ptr, w_dstT]
        irtag = IRTag("unsafe.align_cast", new_alignment=N, old_alignment=old_alignment)

        @vm.register_builtin_func(w_srcT.fqn, "align_cast", [str(N)], irtag=irtag)
        def w_align_cast_impl(vm: "SPyVM", w_ptr: SRC) -> DST:
            if N > old_alignment and w_ptr.addr % N != 0:
                raise SPyError(
                    "W_PanicError",
                    f"align_cast: address 0x{w_ptr.addr:x} not aligned to {N}",
                )
            return W_Ptr(w_dstT, w_ptr.addr, w_ptr.length)  # type: ignore

        return W_OpSpec(w_align_cast_impl, [wam_ptr])

    return w_align_cast_dispatch
