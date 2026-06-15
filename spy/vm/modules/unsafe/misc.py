from spy.errors import WIP
from spy.vm.b import B
from spy.vm.object import W_Type


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

    return True
