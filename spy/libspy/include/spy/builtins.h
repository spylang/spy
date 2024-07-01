#ifndef SPY_BUILTIS_H
#define SPY_BUILTIS_H

#include "spy.h"
#include "spy/str.h"

int32_t
WASM_EXPORT(spy_builtins$abs)(int32_t x);

int32_t
WASM_EXPORT(spy_builtins$abs)(int32_t x);

#ifndef SPY_TARGET_WASM32
void spy_builtins$print_i32(int32_t x);
void spy_builtins$print_f64(double x);
void spy_builtins$print_bool(bool x);
void spy_builtins$print_void(void);
void spy_builtins$print_str(spy_Str *s);

#endif

#endif /* SPY_BUILTIS_H */
