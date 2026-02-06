#include "spy.h"

void *
spy_gc_alloc(size_t size) {
    return malloc(size);
}

void *
spy_raw_alloc(size_t size) {
    return malloc(size);
}
