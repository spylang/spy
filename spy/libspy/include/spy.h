#ifndef SPY_H
#define SPY_H

#include <stdint.h>
#include <stdbool.h>

typedef __SIZE_TYPE__ size_t;

#if defined(SPY_TARGET_WASM32) + defined(SPY_TARGET_EMSCRIPTEN) + defined(SPY_TARGET_NATIVE) == 0
#  error "You must define one and exactly one of the SPY_TARGET_* macros"
#endif


#if defined(SPY_TARGET_NATIVE)
#  define WASM_EXPORT(name) name
# else
#  define WASM_EXPORT(name) \
    __attribute__((export_name(#name))) \
    name
#endif

#ifdef SPY_TARGET_WASM32
static inline void *memcpy(void *dest, const void *src, size_t n) {
    return __builtin_memcpy(dest, src, n);
}

static void _Noreturn abort(void) {
    __builtin_trap();
}
#else
#  include <stdlib.h>
#  include <string.h>
#endif

// this is defined in libc.c. We cannot use __builtin_memcmp :(
int memcmp(const void *s1, const void *s2, size_t n);

// these are defined in walloc.c
void *malloc(size_t size);
void free(void *p);

#include "spy/builtins.h"
#include "spy/str.h"
#include "spy/gc.h"
#include "spy/rawbuffer.h"
#include "spy/debug.h"

#endif /* SPY_H */
