#ifndef SPY_BUILTINS_H
#define SPY_BUILTINS_H

#include "spy.h"
#include "spy/str.h"

static inline int32_t
spy_builtins$hash_i8(int8_t x) {
    if (x == -1) {
        return 2;
    }
    return (int32_t)x;
}

static inline int32_t
spy_builtins$hash_i32(int32_t x) {
    if (x == -1) {
        return 2;
    }
    return x;
}

static inline int32_t
spy_builtins$hash_u8(uint8_t x) {
    return (int32_t)x;
}

static inline int32_t
spy_builtins$hash_bool(bool x) {
    if (x)
        return 1;
    else
        return 0;
}

// spy_flush is not a builtin, but we need it to flush stdout/stderr from
// wastime, see e.g. test_basic.test_print
void WASM_EXPORT(spy_flush)(void);

#endif /* SPY_BUILTINS_H */
