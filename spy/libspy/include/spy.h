#ifndef SPY_H
#define SPY_H

#include <stdint.h>
#include <stdbool.h>

typedef __SIZE_TYPE__ size_t;

#define WASM_EXPORT(name) \
    __attribute__((export_name(#name))) \
    name

static inline void *memcpy(void *dest, const void *src, size_t n) {
    return __builtin_memcpy(dest, src, n);
}

static void _Noreturn abort(void) {
    __builtin_trap();
}

// these are defied in walloc.c
void *malloc(size_t size);
void free(void *p);

#include "spy/builtins.h"
#include "spy/str.h"
#include "spy/gc.h"
#include "spy/debug.h"

#endif /* SPY_H */
