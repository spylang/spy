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
DEFINE_CONV(i8, f64)

DEFINE_CONV(u8, i32)
DEFINE_CONV(u8, f64)

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
    if (y == 0) {
        spy_panic("ZeroDivisionError", "division by zero",
                  __FILE__, __LINE__);
    }
    return (double)x / y;
}

static inline double spy_unsafe$i8_unchecked_div(int8_t x, int8_t y) {
    return (double)x / y;
}

static inline double spy_operator$u8_div(uint8_t x, uint8_t y) {
    if (y == 0) {
        spy_panic("ZeroDivisionError", "division by zero",
                  __FILE__, __LINE__);
    }
    return (double)x / y;
}

static inline double spy_unsafe$u8_unchecked_div(uint8_t x, uint8_t y) {
    return (double)x / y;
}

static inline double spy_operator$i32_div(int32_t x, int32_t y) {
    if (y == 0) {
        spy_panic("ZeroDivisionError", "division by zero",
                  __FILE__, __LINE__);
    }
    return (double)x / y;
}

static inline double spy_unsafe$i32_unchecked_div(int32_t x, int32_t y) {
    return (double)x / y;
}

static inline int8_t spy_operator$i8_floordiv(int8_t x, int8_t y) {
    if (y == 0) {
        spy_panic("ZeroDivisionError", "integer division or modulo by zero",
                  __FILE__, __LINE__);
    }
    int8_t q = x / y;
    int8_t r = x % y;

    if ((r != 0) && ((x ^ y) < 0)) {
        q -= 1;
    }

    return q;
}

static inline int8_t spy_unsafe$i8_unchecked_floordiv(int8_t x, int8_t y) {
    int8_t q = x / y;
    int8_t r = x % y;

    if ((r != 0) && ((x ^ y) < 0)) {
        q -= 1;
    }

    return q;
}

static inline uint8_t spy_operator$u8_floordiv(uint8_t x, uint8_t y) {
    if (y == 0) {
        spy_panic("ZeroDivisionError", "integer division or modulo by zero",
                  __FILE__, __LINE__);
    }
    return x / y;
}

static inline int32_t spy_operator$i32_floordiv(int32_t x, int32_t y) {
    if (y == 0) {
        spy_panic("ZeroDivisionError", "integer division or modulo by zero",
                  __FILE__, __LINE__);
    }
    int32_t q = x / y;
    int32_t r = x % y;

    if ((r != 0) && ((x ^ y) < 0)) {
        q -= 1;
    }

    return q;
}

static inline int32_t spy_unsafe$i32_unchecked_floordiv(int32_t x, int32_t y) {
    int32_t q = x / y;
    int32_t r = x % y;

    if ((r != 0) && ((x ^ y) < 0)) {
        q -= 1;
    }

    return q;
}

static inline int8_t spy_operator$i8_mod(int8_t x, int8_t y) {
    if (y == 0) {
        spy_panic("ZeroDivisionError", "integer modulo by zero",
                  __FILE__, __LINE__);
    }
    int8_t r = x % y;

    if ((r != 0) && ((x ^ y) < 0)) {
        r += y;
    }

    return r;
}

static inline int8_t spy_unsafe$i8_unchecked_mod(int8_t x, int8_t y) {
    int8_t r = x % y;

    if ((r != 0) && ((x ^ y) < 0)) {
        r += y;
    }

    return r;
}


static inline double spy_operator$u8_mod(uint8_t x, uint8_t y) {
    if (y == 0) {
        spy_panic("ZeroDivisionError", "integer modulo by zero",
                  __FILE__, __LINE__);
    }
    return x % y;
}

static inline int32_t spy_operator$i32_mod(int32_t x, int32_t y) {
    if (y == 0) {
        spy_panic("ZeroDivisionError", "integer modulo by zero",
                  __FILE__, __LINE__);
    }
    int32_t r = x % y;

    if ((r != 0) && ((x ^ y) < 0)) {
        r += y;
    }

    return r;
}

static inline int32_t spy_unsafe$i32_unchecked_mod(int32_t x, int32_t y) {
    int32_t r = x % y;

    if ((r != 0) && ((x ^ y) < 0)) {
        r += y;
    }

    return r;
}

static inline double spy_operator$f64_div(double x, double y) {
    if (y == 0) {
        spy_panic("ZeroDivisionError", "float division by zero",
                  __FILE__, __LINE__);
    }
    return x / y;
}

static inline double spy_operator$f64_floordiv(double x, double y) {
    if (y == 0) {
        spy_panic("ZeroDivisionError", "float floor division by zero",
                  __FILE__, __LINE__);
    }
    return floor(x / y);
}

static inline double spy_unsafe$f64_unchecked_floordiv(double x, double y) {
    return floor(x / y);
}

static inline double spy_operator$f64_mod(double x, double y) {
    if (y == 0) {
        spy_panic("ZeroDivisionError", "float modulo by zero",
                  __FILE__, __LINE__);
    }
    double r = fmod(x, y);

    if (r != 0.00 && (y < 0.00) != (r < 0.00)) {
        r += y;
    }

    return r;
}

static inline double spy_unsafe$f64_unchecked_mod(double x, double y) {
    double r = fmod(x, y);

    if (r != 0.00 && (y < 0.00) != (r < 0.00)) {
        r += y;
    }

    return r;
}

static inline bool spy_operator$bool_eq(bool x, bool y) {
    return x == y;
}

static inline bool spy_operator$bool_ne(bool x, bool y) {
    return x != y;
}

static inline bool spy_operator$bool_and(bool x, bool y) {
    return x && y;
}

static inline bool spy_operator$bool_or(bool x, bool y) {
    return x || y;
}

static inline bool spy_operator$bool_xor(bool x, bool y) {
    return x != y;
}

static inline bool spy_operator$bool_lt(bool x, bool y) {
    return !x && y;
}

static inline bool spy_operator$bool_le(bool x, bool y) {
    return !x || y;
}

static inline bool spy_operator$bool_gt(bool x, bool y) {
    return x && !y;
}

static inline bool spy_operator$bool_ge(bool x, bool y) {
    return x || !y;
}

static inline bool spy_operator$bool_not(bool x) {
    return !x;
}

#endif /* SPY_OPERATOR_H */
