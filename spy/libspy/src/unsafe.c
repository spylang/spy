#include "spy.h"

void *
spy_nogc_alloc(size_t size) {
    return malloc(size);
}

void *
spy_raw_alloc(size_t size) {
    return malloc(size);
}

void *
spy_raw_alloc_aligned(size_t size, size_t alignment) {
    if (alignment <= SPY_BASE_ALIGNMENT)
        return spy_raw_alloc(size);
    return SPY_ALIGN_UP(spy_raw_alloc(size + alignment), alignment);
}

void *
spy_nogc_alloc_aligned(size_t size, size_t alignment) {
    if (alignment <= SPY_BASE_ALIGNMENT)
        return spy_nogc_alloc(size);
    return SPY_ALIGN_UP(spy_nogc_alloc(size + alignment), alignment);
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
