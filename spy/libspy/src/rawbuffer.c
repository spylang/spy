#include "spy.h"

spy_RawBuffer
spy_rawbuffer__rb_alloc(size_t size) {
    spy_RawBuffer rb;
    rb.buf = (char *)spy_GcAlloc(size).p;
    return rb;
}

void
spy_rawbuffer__rb_set_i32(spy_RawBuffer rb, int32_t offset, int32_t val) {
    int32_t *p = (int32_t *)(rb.buf + offset);
    *p = val;
}

int32_t
spy_rawbuffer__rb_get_i32(spy_RawBuffer rb, int32_t offset) {
    int32_t *p = (int32_t *)(rb.buf + offset);
    return *p;
}
