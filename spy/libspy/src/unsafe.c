#include "spy.h"

void *
spy_nogc_alloc(size_t size) {
    return malloc(size);
}

void *
spy_raw_alloc(size_t size) {
    return malloc(size);
}

// Aligned variants for the interp (vm.ll.call) path.
void *
spy_raw_alloc_aligned(size_t size, size_t alignment) {
    return spy_alloc_aligned_impl(size, alignment, spy_raw_alloc);
}

void *
spy_nogc_alloc_aligned(size_t size, size_t alignment) {
    return spy_alloc_aligned_impl(size, alignment, spy_nogc_alloc);
}

void
_spy_memcpy(void *dst, void *src, size_t n) {
    memcpy(dst, src, n);
}

void
_spy_memmove(void *dst, void *src, size_t n) {
    memmove(dst, src, n);
}

void
_spy_memset(void *dst, int value, size_t n) {
    memset(dst, value, n);
}

int32_t
_spy_memcmp(void *a, void *b, size_t n) {
    return memcmp(a, b, n);
}
