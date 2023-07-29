#ifndef SPY_H
#define SPY_H

#include <stdint.h>
#include <stdbool.h>

typedef __SIZE_TYPE__ size_t;
#define WASM_EXPORT(name) __attribute__((export_name(name)))

static inline void *memcpy(void *dest, const void *src, size_t n) {
    return __builtin_memcpy(dest, src, n);
}

// these are defied in walloc.c
void *malloc(size_t size);
void free(void *p);

#include "spy/str.h"
#include "spy/gc.h"

#endif /* SPY_H */
