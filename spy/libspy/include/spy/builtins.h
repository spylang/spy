#ifndef SPY_BUILTINS_H
#define SPY_BUILTINS_H

#include "spy.h"
#include "spy/str.h"

int32_t WASM_EXPORT(spy_builtins$abs)(int32_t x);

int32_t WASM_EXPORT(spy_builtins$min)(int32_t x, int32_t y);

int32_t WASM_EXPORT(spy_builtins$max)(int32_t x, int32_t y);

void WASM_EXPORT(spy_builtins$print_i32)(int32_t x);

void WASM_EXPORT(spy_builtins$print_f64)(double x);

void WASM_EXPORT(spy_builtins$print_bool)(bool x);

void WASM_EXPORT(spy_builtins$print_NoneType)(void);

void WASM_EXPORT(spy_builtins$print_str)(spy_Str *s);

static inline int32_t
WASM_EXPORT(spy_builtins$hash_i8)(int8_t x) {
    if (x == -1) {
        return 2;
    }
    return (int32_t)x;
}

static inline int32_t
WASM_EXPORT(spy_builtins$hash_i32)(int32_t x) {
    if (x == -1) {
        return 2;
    }
    return x;
}

static inline int32_t
WASM_EXPORT(spy_builtins$hash_u8)(uint8_t x) {
    return (int32_t)x;
}

static inline int32_t
WASM_EXPORT(spy_builtins$hash_bool)(bool x) {
    if (x)
        return 1;
    else
        return 0;
}

// spy_flush is not a builtin, but we need it to flush stdout/stderr from
// wastime, see e.g. test_basic.test_print
void WASM_EXPORT(spy_flush)(void);

#endif /* SPY_BUILTINS_H */
