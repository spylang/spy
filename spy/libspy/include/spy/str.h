#ifndef SPY_STR_H
#define SPY_STR_H

#include <stddef.h>

typedef struct {
    size_t length;
    const char utf8[];
} spy_Str;

spy_Str *
WASM_EXPORT(spy_StrAlloc)(size_t length);

spy_Str *
WASM_EXPORT(spy_StrAdd)(spy_Str *a, spy_Str *b);

#endif /* SPY_STR_H */
