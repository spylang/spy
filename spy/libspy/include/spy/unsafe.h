#ifndef SPY_UNSAFE_H
#define SPY_UNSAFE_H

#include "spy.h"

spy_GcRef
WASM_EXPORT(spy_gc_alloc_mem)(size_t size);

static inline int32_t *spy_unsafe$gc_alloc(size_t n) {
    spy_GcRef r = spy_gc_alloc_mem(sizeof(int32_t) * n);
    return (int32_t *)(r.p);
}

static inline int32_t spy_unsafe$i32ptr_get(int32_t *p, int32_t i) {
    return p[i];
}

static inline void spy_unsafe$i32ptr_set(int32_t *p, int32_t i, int32_t v) {
    p[i] = v;
}


#endif /* SPY_UNSAFE_H */
