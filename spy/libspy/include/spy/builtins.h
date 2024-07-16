#ifndef SPY_BUILTINS_H
#define SPY_BUILTINS_H

#include "spy.h"
#include "spy/str.h"

int32_t
WASM_EXPORT(spy_builtins$abs)(int32_t x);

void
WASM_EXPORT(spy_builtins$print_i32)(int32_t x);

void
WASM_EXPORT(spy_builtins$print_f64)(double x);

void
WASM_EXPORT(spy_builtins$print_bool)(bool x);

void
WASM_EXPORT(spy_builtins$print_void)(void);

void
WASM_EXPORT(spy_builtins$print_str)(spy_Str *s);

// spy_flush is not a builtin, but we need it to flush stdout/stderr from
// wastime, see e.g. test_basic.test_print
void
WASM_EXPORT(spy_flush)(void);

#endif /* SPY_BUILTINS_H */
