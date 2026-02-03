#include "spy.h"

spy_GcRef
spy_gc_alloc_mem(size_t size) {
    return spy_GcAlloc(size);
}

void *
spy_raw_alloc(size_t size) {
    return malloc(size);
}
