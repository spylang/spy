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

// XXX: should we introduce a separate type Char?
spy_Str *
WASM_EXPORT(spy_str_getitem)(spy_Str *s, int32_t i);

#define spy_builtins_ops__str_add spy_str_add
#define spy_builtins_ops__str_mul spy_str_mul
#define spy_builtins_ops__str_getitem spy_str_getitem

#endif /* SPY_STR_H */
