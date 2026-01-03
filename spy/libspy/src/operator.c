#include "spy.h"
#include <math.h>
#include <stdbool.h>

float
spy_operator$f32_add(float a, float b) {
    return a + b;
}

float
spy_operator$f32_sub(float x, float y) {
    return x - y;
}

float
spy_operator$f32_mul(float x, float y) {
    return x * y;
}

float
spy_operator$f32_div(float x, float y) {
    if (y == 0) {
        spy_panic("ZeroDivisionError", "float division by zero", __FILE__, __LINE__);
    }
    return x / y;
}

float
spy_unsafe$f32_ieee754_div(float x, float y) {
    return x / y;
}

float
spy_unsafe$f32_unchecked_div(float x, float y) {
#ifdef SPY_DEBUG
    if (y == 0) {
        spy_panic("PanicError", "float division by zero", __FILE__, __LINE__);
    }
#endif
    return x / y;
}

float
spy_operator$f32_floordiv(float x, float y) {
    if (y == 0) {
        spy_panic(
            "ZeroDivisionError", "float floor division by zero", __FILE__, __LINE__
        );
    }
    return floorf(x / y);
}

float
spy_unsafe$f32_unchecked_floordiv(float x, float y) {
#ifdef SPY_DEBUG
    if (y == 0) {
        spy_panic("PanicError", "float floor division by zero", __FILE__, __LINE__);
    }
#endif
    return floorf(x / y);
}

float
spy_operator$f32_mod(float x, float y) {
    if (y == 0) {
        spy_panic("ZeroDivisionError", "float modulo by zero", __FILE__, __LINE__);
    }
    float r = fmodf(x, y);

    if (r != 0.00 && (y < 0.00) != (r < 0.00)) {
        r += y;
    }

    return r;
}

float
spy_unsafe$f32_unchecked_mod(float x, float y) {
#ifdef SPY_DEBUG
    if (y == 0) {
        spy_panic("PanicError", "float modulo by zero", __FILE__, __LINE__);
    }
#endif
    float r = fmodf(x, y);

    if (r != 0.00 && (y < 0.00) != (r < 0.00)) {
        r += y;
    }

    return r;
}

bool
spy_operator$f32_eq(float x, float y) {
    return x == y;
}

bool
spy_operator$f32_ne(float x, float y) {
    return x != y;
}

bool
spy_operator$f32_lt(float x, float y) {
    return x < y;
}

bool
spy_operator$f32_le(float x, float y) {
    return x <= y;
}

bool
spy_operator$f32_gt(float x, float y) {
    return x > y;
}

bool
spy_operator$f32_ge(float x, float y) {
    return x >= y;
}

float
spy_operator$f32_neg(float x) {
    return -x;
}
