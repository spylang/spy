#ifndef SPY_STR_H
#define SPY_STR_H

#include <stddef.h>
#include "spy.h"

typedef struct {
    size_t length;
    const char utf8[];
} spy_Str;

spy_Str *
WASM_EXPORT(spy_str_alloc)(size_t length);

spy_Str *
WASM_EXPORT(spy_str_add)(spy_Str *a, spy_Str *b);

spy_Str *
WASM_EXPORT(spy_str_mul)(spy_Str *a, int32_t b);

bool
WASM_EXPORT(spy_str_eq)(spy_Str *a, spy_Str *b);

static inline bool
spy_str_ne(spy_Str *a, spy_Str *b) {
    return !spy_str_eq(a, b);
}

// XXX: should we introduce a separate type Char?
spy_Str *
WASM_EXPORT(spy_str_getitem)(spy_Str *s, int32_t i);

int32_t
WASM_EXPORT(spy_str_len)(spy_Str *s);

spy_Str *
WASM_EXPORT(spy_builtins$int2str)(int32_t x);

spy_Str *
WASM_EXPORT(spy_builtins$float2str)(double x);


#define spy_operator$str_add spy_str_add
#define spy_operator$str_mul spy_str_mul
#define spy_operator$str_eq  spy_str_eq
#define spy_operator$str_ne  spy_str_ne
#define spy_builtins$str$__getitem__ spy_str_getitem
#define spy_builtins$str$__len__ spy_str_len

#endif /* SPY_STR_H */
