#ifndef SPY_RAW_BUFFER_H
#define SPY_RAW_BUFFER_H

#include <stddef.h>
#include "spy.h"

typedef struct {
    char *buf;
} spy_RawBuffer;

spy_RawBuffer
WASM_EXPORT(spy_rawbuffer__rb_alloc)(size_t size);

void
WASM_EXPORT(spy_rawbuffer__rb_set_i32)(spy_RawBuffer rb,
                                       int32_t offset, int32_t val);

int32_t
WASM_EXPORT(spy_rawbuffer__rb_get_i32)(spy_RawBuffer rb, int32_t offset);


#endif /* SPY_RAW_BUFFER_H */
