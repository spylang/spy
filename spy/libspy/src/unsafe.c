#include "spy.h"

void *
spy_gc_alloc(size_t size) {
    return malloc(size);
}

void *
spy_raw_alloc(size_t size) {
    return malloc(size);
}

void
_spy_memcpy(void *dst, void *src, size_t n) {
    memcpy(dst, src, n);
}

void
_spy_memmove(void *dst, void *src, size_t n) {
    memmove(dst, src, n);
}
