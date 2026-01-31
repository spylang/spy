from spy.errors import WIP
from spy.vm.b import B
from spy.vm.object import W_Type


def sizeof(w_T: W_Type) -> int:
    from spy.vm.modules.unsafe.ptr import W_RawPtrType
    from spy.vm.struct import W_StructType

    if w_T in (B.w_i8, B.w_u8):
        return 1
    elif w_T is B.w_i32:
        return 4
    elif w_T is B.w_f64:
        return 8
    elif isinstance(w_T, W_StructType):
        return w_T.size
    elif isinstance(w_T, W_RawPtrType) or w_T is B.w_str:
        # w_str is a "spy_Str *" in C, so it's a pointer.
        #
        # XXX what is the right size of pointers? For wasm32 is 4 of course,
        # but for native it might be 8. Does it mean that we need to
        # preemptively choose the target platform BEFORE redshifting?
        return 4 + 4  # in debug mode we store both addr and length
    else:
        raise WIP(f"sizeof({w_T}) not implemented")
