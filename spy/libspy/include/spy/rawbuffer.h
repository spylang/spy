#ifndef SPY_RAW_BUFFER_H
#define SPY_RAW_BUFFER_H

#include "spy.h"
#include <stdalign.h>
#include <stddef.h>

// RawBuffer is implemented entirely as static inline functions, since they
// are all super-simple and we want the optimizer to be able to see through
// them

typedef struct {
    size_t length;
    _Alignas(double) char buf[];
} spy_RawBuffer;

static inline spy_RawBuffer *
spy_rawbuffer$rb_alloc(size_t length) {
    size_t size = sizeof(spy_RawBuffer) + length;
    spy_RawBuffer *rb = (spy_RawBuffer *)spy_GcAlloc(size).p;
    rb->length = length;
    return rb;
}

static inline void
spy_rawbuffer$rb_set_i32(spy_RawBuffer *rb, int32_t offset, int32_t val) {
    if (offset < 0 || (size_t)offset + sizeof(int32_t) > rb->length)
        spy_panic("rb_set_i32: out of bounds");
    int32_t *p = (int32_t *)(rb->buf + offset);
    *p = val;
}

static inline int32_t
spy_rawbuffer$rb_get_i32(spy_RawBuffer *rb, int32_t offset) {
    if (offset < 0 || (size_t)offset + sizeof(int32_t) > rb->length)
        spy_panic("rb_get_i32: out of bounds");
    int32_t *p = (int32_t *)(rb->buf + offset);
    return *p;
}

static inline void
spy_rawbuffer$rb_set_f64(spy_RawBuffer *rb, int32_t offset, double val) {
    if (offset < 0 || (size_t)offset + sizeof(double) > rb->length)
        spy_panic("rb_set_f64: out of bounds");
    double *p = (double *)(rb->buf + offset);
    *p = val;
}

static inline double
spy_rawbuffer$rb_get_f64(spy_RawBuffer *rb, int32_t offset) {
    if (offset < 0 || (size_t)offset + sizeof(double) > rb->length)
        spy_panic("rb_get_f64: out of bounds");
    double *p = (double *)(rb->buf + offset);
    return *p;
}

#endif /* SPY_RAW_BUFFER_H */
