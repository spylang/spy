#ifndef SPY_OPERATOR_H
#define SPY_OPERATOR_H

#include <math.h>
#include "spy.h"
#include "spy/debug.h"


// DEFINE_CONV emits something like:
//  static inline int32_t spy_operator$f64_to_i32(double x) { return x; }
#define DEFINE_CONV(FROM, TO) \
    static inline TO spy_operator$##FROM##_to_##TO(FROM x) { return x; }

#define i8 int8_t
#define u8 uint8_t
#define i32 int32_t
#define f64 double

DEFINE_CONV(i32, bool)
DEFINE_CONV(i32, i8)
DEFINE_CONV(i32, u8)
DEFINE_CONV(i32, f64)
DEFINE_CONV(i8, i32)
DEFINE_CONV(u8, i32)

#undef i8
#undef u8
#undef i32
#undef f64

// implement rust-like saturating conversion.
static inline int32_t spy_operator$f64_to_i32(double x) {
    // Ideally, we would like to use compiler intrinsics and/or CPU
    // instruction which implement this exact logic: with gcc/clang on x86_64
    // it seems that a simple C-level cast does the trick, but notably this
    // doesn't work on WASM32. So for now, we just implement the logic
    // explicitly.
    if (isnan(x)) return 0;
    if (x > INT32_MAX) return INT32_MAX;
    if (x < INT32_MIN) return INT32_MIN;
    return (int32_t)x;  // Safe since we handled out-of-range cases
}

static inline void spy_operator$raise(spy_Str *etype,
                                      spy_Str *message,
                                      spy_Str *fname,
                                      int32_t lineno) {
    spy_panic(etype->utf8, message->utf8, fname->utf8, lineno);
}

static inline double spy_operator$i8_div(int8_t x, int8_t y) {
    return (double)x / y;
}

static inline double spy_operator$u8_div(uint8_t x, uint8_t y) {
    return (double)x / y;
}

static inline double spy_operator$i32_div(int32_t x, int32_t y) {
    return (double)x / y;
}

static inline double spy_operator$f64_floordiv(double x, double y) {
    return floor(x / y);
}

#endif /* SPY_OPERATOR_H */
