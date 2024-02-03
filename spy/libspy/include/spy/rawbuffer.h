#ifndef SPY_RAW_BUFFER_H
#define SPY_RAW_BUFFER_H

#include <stddef.h>
#include "spy.h"

// RawBuffer is implemented entirely as static inline functions, since they
// are all super-simple and we want the optimizer to be able to see through
// them

typedef struct {
    char *buf;
} spy_RawBuffer;

static inline spy_RawBuffer
spy_rawbuffer__rb_alloc(size_t size) {
    spy_RawBuffer rb;
    rb.buf = (char *)spy_GcAlloc(size).p;
    return rb;
}

static inline void
spy_rawbuffer__rb_set_i32(spy_RawBuffer rb, int32_t offset, int32_t val) {
    int32_t *p = (int32_t *)(rb.buf + offset);
    *p = val;
}

static inline int32_t
spy_rawbuffer__rb_get_i32(spy_RawBuffer rb, int32_t offset) {
    int32_t *p = (int32_t *)(rb.buf + offset);
    return *p;
}


#endif /* SPY_RAW_BUFFER_H */
