from typing import TYPE_CHECKING

from spy.errors import WIP, SPyError
from spy.vm.b import B
from spy.vm.object import W_Type
from spy.vm.primitive import W_I32

from . import UNSAFE

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


def sizeof(w_T: W_Type) -> int:
    from spy.vm.modules.posix import POSIX
    from spy.vm.modules.unsafe.ptr import W_PtrType
    from spy.vm.struct import W_StructType

    if w_T in (B.w_bool, B.w_i8, B.w_u8):
        return 1
    elif w_T in (B.w_i32, B.w_u32, B.w_f32):
        return 4
    elif w_T in (B.w_i64, B.w_u64, B.w_f64):
        return 8
    elif isinstance(w_T, W_StructType):
        return w_T.size
    elif isinstance(w_T, W_PtrType) or w_T is B.w_str:
        # w_str is a "spy_StrObject *" in C, so it's a pointer.
        #
        # XXX what is the right size of pointers? For wasm32 is 4 of course,
        # but for native it might be 8. Does it mean that we need to
        # preemptively choose the target platform BEFORE redshifting?
        return 4 + 4  # in debug mode we store both addr and length
    elif w_T is POSIX.w__FILE:
        return 4  # XXX
    else:
        raise WIP(f"sizeof({w_T}) not implemented")


def contains_gc_ptr(w_T: W_Type) -> bool:
    """
    Return True if a value of type `w_T` may itself contain (transitively)
    a gc_ptr/gc_ref, i.e. memory that the GC needs to be able to scan and
    collect.

    This is used to decide whether `gc_alloc[T]` can use GC_MALLOC_ATOMIC
    (for pointer-free T, e.g. arrays of f64/i32/u8/...) instead of
    GC_MALLOC. Using GC_MALLOC_ATOMIC for a T that contains a gc_ptr would
    be a memory-safety bug: the collector wouldn't see the reference and
    could free still-reachable memory.

    We are conservative: any type we don't explicitly know to be
    pointer-free is treated as if it *might* contain a pointer.
    """
    from spy.vm.modules.unsafe.ptr import W_PtrType, W_RefType
    from spy.vm.object import W_Type
    from spy.vm.struct import W_StructType

    # primitive numeric/bool types: definitely pointer-free
    if w_T in (
        B.w_bool,
        B.w_i8,
        B.w_u8,
        B.w_i32,
        B.w_u32,
        B.w_f32,
        B.w_f64,
    ):
        return False

    if isinstance(w_T, (W_PtrType, W_RefType)):
        return True

    if w_T is B.w_str:
        return True

    if isinstance(w_T, W_StructType):
        return any(contains_gc_ptr(w_field.w_T) for w_field in w_T.iterfields_w())

    if isinstance(w_T, W_Type):
        return True

    raise NotImplementedError(f"{w_T=}")


def alignof(w_T: W_Type) -> int:
    """
    The natural alignment of a type, in bytes.
    """
    from spy.vm.struct import W_StructType

    # for every scalar type SPy has today, natural alignment == size
    if w_T in (B.w_bool, B.w_i8, B.w_u8):
        return 1
    elif w_T in (B.w_i32, B.w_u32, B.w_f32):
        return 4
    elif w_T in (B.w_i64, B.w_u64, B.w_f64):
        return 8
    elif isinstance(w_T, W_StructType):
        if not w_T.is_defined():
            # not-yet-defined struct (e.g. a struct that (transitively)
            # points to itself, or one of the special bootstrapping
            # struct types like _str::StrObject that this function may be
            # asked about before its fields are populated -- see the
            # analogous comment in W_MemLocType.from_itemtype). We can't
            # look at fields that don't exist yet, so fall back to 1
            # rather than crashing;
            return 1
        # the usual "max of the fields' alignments" rule. A struct with no
        # fields has nothing to take the max over, so fall back to 1
        # (matching a struct of size 0) rather than raising.
        aligns = [alignof(w_field.w_T) for w_field in w_T.iterfields_w()]
        return max(aligns, default=1)
    else:
        # tmp: we don't know, better than crashing
        return 1


@UNSAFE.builtin_func(color="blue")
def w_alignof(vm: "SPyVM", w_T: W_Type) -> W_I32:
    """
    The SPy-visible `alignof(T)` blue builtin.
    """
    return vm.wrap(alignof(w_T))


def parse_optional_alignment(
    vm: "SPyVM", w_T: W_Type, args_w: tuple, funcname: str
) -> int:
    """
    Shared arg-parsing for the optional, defaulted alignment type param on
    {raw,gc}_ptr[T, N=alignof(T)] / {raw,gc}_alloc[T, N=alignof(T)].
    `args_w` is whatever extra positional blue args were
    passed after `T`: zero (use the default) or one (an i32 `N`).
    """
    if len(args_w) == 0:
        return alignof(w_T)
    elif len(args_w) == 1:
        w_N = args_w[0]
        if not isinstance(w_N, W_I32):
            t = vm.dynamic_type(w_N).fqn.human_name(vm)
            raise SPyError(
                "W_TypeError", f"{funcname}: alignment must be i32, got `{t}`"
            )
        return int(vm.unwrap_i32(w_N))
    else:
        n = len(args_w) + 1
        raise SPyError("W_TypeError", f"{funcname} accepts 1 or 2 arguments, got {n}")
