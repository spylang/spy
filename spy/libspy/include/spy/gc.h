#ifndef SPY_GC_H
#define SPY_GC_H

#include "spy.h"

typedef struct {
    void *p;
} spy_GcRef;

// for now the GC is a fake, we just malloc and leak
static inline spy_GcRef spy_GcAlloc(size_t size) {
    return (spy_GcRef){malloc(size)};
}

#endif /* SPY_GC_H */
