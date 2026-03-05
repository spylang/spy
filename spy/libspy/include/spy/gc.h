#ifndef SPY_GC_H
#define SPY_GC_H

#include "spy.h"

typedef struct {
    void *p;
} spy_GcRef;

#ifdef SPY_GC_BDWGC
#include <gc.h>

static inline spy_GcRef
spy_GcAlloc(size_t size) {
    return (spy_GcRef){GC_MALLOC(size)};
}

#else
// default: no GC, just malloc and leak
static inline spy_GcRef
spy_GcAlloc(size_t size) {
    return (spy_GcRef){malloc(size)};
}

#endif

#endif /* SPY_GC_H */
