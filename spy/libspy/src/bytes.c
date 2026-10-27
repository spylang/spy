#include "spy.h"
#include <stddef.h>
#include <stdint.h>

_spy_BytesObject_Layout
_spy_BytesObject_layout(void) {
    return (_spy_BytesObject_Layout){
        .size = sizeof(spy_BytesObject),
        .length_offset = offsetof(spy_BytesObject, length),
        .hash_offset = offsetof(spy_BytesObject, hash),
        .data_offset = offsetof(spy_BytesObject, data),
    };
}

spy_BytesObject *
spy_bytes_alloc(size_t length) {
    // allocate a spy_BytesObject AND the data buffer as a single allocation
    size_t size = sizeof(spy_BytesObject) + length;
    spy_BytesObject *res = (spy_BytesObject *)spy_GcAlloc(size).p;
    res->length = length;
    res->hash = -1; // unsealed
#ifdef SPY_DEBUG
    res->data = (spy_gc_ptr_u8){(uint8_t *)(res + 1), (ptrdiff_t)length};
#else
    res->data = (spy_gc_ptr_u8){(uint8_t *)(res + 1)};
#endif
    return res;
}

void
spy_bytes_seal(spy_BytesObject *b) {
    SPY_BYTES_ASSERT_UNSEALED(b);
    b->hash = 0;
}

int32_t
spy_bytes_hash(spy_BytesObject *b) {
    int32_t h = b->hash;
    // NOTE: we cannot use SPY_BYTES_ASSERT_UNSEALED because we want to do the check
    // also in release mode; spy_bytes_alloc sets hash == -1, we don't want to mistake
    // it for "hash already computed".
    //
    // The assumption is that the extra check here is cheap enough to keep. If it turns
    // out to be too costly, the solution is to modify spy_bytes_alloc to set hash=0 in
    // SPY_RELEASE mode.
    if (h == -1)
        spy_panic("PanicError", "bytes is not sealed", __FILE__, __LINE__);
    if (h != 0)
        return h;
    // FNV-1a hash (same algorithm as str; hashes not required to match)
    // NOTE: must stay in C because applevel SPy has no wrapping i32 multiply yet
    uint32_t x = 2166136261u;
    for (size_t i = 0; i < b->length; i++) {
        x ^= spy_BytesObject_DATA(b)[i];
        x *= 16777619u;
    }
    int32_t result = (int32_t)x;
    if (result == -1)
        result = -2;
    if (result == 0)
        result = 1;
    b->hash = result;
    return result;
}
