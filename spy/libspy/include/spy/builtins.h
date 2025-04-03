#ifndef SPY_BUILTINS_H
#define SPY_BUILTINS_H

#include "spy.h"
#include "spy/str.h"

int32_t
WASM_EXPORT(spy_builtins$abs)(int32_t x);

int32_t
WASM_EXPORT(spy_builtins$min)(int32_t x, int32_t y);

int32_t
WASM_EXPORT(spy_builtins$max)(int32_t x, int32_t y);

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


#define SPY_TYPELIFT_FUNCTIONS(HL, LL)          \
    static inline HL HL##$__lift__(LL ll) {     \
        return (HL){ll};                        \
    }                                           \
    static inline LL HL##$__unlift__(HL hl) {   \
        return hl.ll;                           \
    }

#endif /* SPY_BUILTINS_H */
