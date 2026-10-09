"""
Pointer type casting and alignment casting for the unsafe module.

Provides:
- align_cast[N](ptr): changes alignment tag, preserves address and item type
"""

from typing import TYPE_CHECKING, Annotated

from spy.errors import SPyError
from spy.vm.irtag import IRTag
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_I32, W_Dynamic
from spy.vm.w import W_Type

from . import UNSAFE
from .misc import W_Align, sizeof
from .ptr import W_Ptr, W_PtrType, w_gc_ptr, w_raw_ptr

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


def _check_ptr_static(vm: "SPyVM", wam_ptr: W_MetaArg, opname: str) -> W_PtrType:
    """
    Validate that wam_ptr is statically typed as ptr[T].
    """
    w_T = wam_ptr.w_static_T
    if isinstance(w_T, W_PtrType):
        return w_T
    t = w_T.fqn.human_name(vm)
    err = SPyError("W_TypeError", "mismatched types")
    err.add("error", f"{opname}: expected ptr[T], got `{t}`", loc=wam_ptr.loc)
    raise err


def _ptrtype_like(
    vm: "SPyVM", w_srcT: W_PtrType, w_itemT: W_Type, alignment: int
) -> W_PtrType:
    """
    Return a ptr type like `w_srcT`, but with another item type and alignment.
    """
    w_ctor = w_raw_ptr if w_srcT.memkind == "raw" else w_gc_ptr
    w_dstT = vm.fast_call(w_ctor, [w_itemT, W_Align(alignment)])
    assert isinstance(w_dstT, W_PtrType)
    vm.make_fqn_const(w_dstT)
    return w_dstT


@UNSAFE.builtin_func(color="blue", kind="generic")
def w_align_cast(vm: "SPyVM", w_N: W_I32) -> W_Dynamic:
    """
    align_cast[N](ptr)

    It produces raw_ptr[T, align(N)]/gc_ptr[T, align(N)]
    (same memkind and item type as the source, new alignment N):

    - Weakening (N <= src_align): free conversion, always safe. Note
      this is also handled implicitly by W_CONVERT_TO for plain assignment;
    - Strengthening (N > src_align): asserts addr % N == 0 in DEBUG mode;
      trusts the claim in RELEASE mode.
    """
    N = vm.unwrap_i32(w_N)
    ns = UNSAFE.w_align_cast.fqn.with_qualifiers([str(N)])

    @vm.register_builtin_func(ns, "impl", color="blue", kind="metafunc")
    def w_align_cast_dispatch(vm: "SPyVM", wam_ptr: W_MetaArg) -> W_OpSpec:
        w_srcT = _check_ptr_static(vm, wam_ptr, "align_cast")
        src_align = w_srcT.resolved_alignment()
        w_dstT = _ptrtype_like(vm, w_srcT, w_srcT.w_itemT, N)

        SRC = Annotated[W_Ptr, w_srcT]
        DST = Annotated[W_Ptr, w_dstT]
        irtag = IRTag("unsafe.align_cast", dst_align=N, src_align=src_align)

        @vm.register_builtin_func(w_srcT.fqn, "align_cast", [str(N)], irtag=irtag)
        def w_align_cast_impl(vm: "SPyVM", w_ptr: SRC) -> DST:
            if N > src_align and w_ptr.addr % N != 0:
                raise SPyError(
                    "W_PanicError",
                    f"align_cast: address 0x{w_ptr.addr:x} not aligned to {N}",
                )
            return W_Ptr(w_dstT, w_ptr.addr, w_ptr.length)  # type: ignore

        return W_OpSpec(w_align_cast_impl, [wam_ptr])

    return w_align_cast_dispatch
