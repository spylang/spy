#ifndef SPY_COMPLEX_H
#define SPY_COMPLEX_H

#include "spy.h"
#include "spy/debug.h"
#include <complex.h>
#include <ctype.h>
#include <errno.h>
#include <math.h>
#include <stdio.h>

typedef struct {
    double real;
    double imag;
} spy_Complex128;

#define spy_builtins$complex128$__get_real__ spy_complex128_get_real
#define spy_builtins$complex128$__get_imag__ spy_complex128_get_imag
#define spy_builtins$complex128$conjugate spy_complex128_conjugate

static inline double
spy_complex128_get_real(spy_Complex128 x) {
    return x.real;
}

static inline double
spy_complex128_get_imag(spy_Complex128 x) {
    return x.imag;
}

static inline spy_Complex128
spy_complex128_conjugate(spy_Complex128 x) {
    return (spy_Complex128){.real = x.real, .imag = -x.imag};
}

static inline spy_Complex128
spy_operator$i32_to_complex128(int32_t x) {
    return (spy_Complex128){.real = (double)x};
}

static inline spy_Complex128
spy_operator$f64_to_complex128(double x) {
    return (spy_Complex128){.real = x};
}

static inline spy_Complex128
spy_operator$f64_f64_to_complex128(double x, double y) {
    return (spy_Complex128){.real = x, .imag = y};
}

static inline spy_Complex128
spy_operator$complex128_add(spy_Complex128 x, spy_Complex128 y) {
    return (spy_Complex128){.real = x.real + y.real, .imag = x.imag + y.imag};
}

static inline spy_Complex128
spy_operator$complex128_sub(spy_Complex128 x, spy_Complex128 y) {
    return (spy_Complex128){.real = x.real - y.real, .imag = x.imag - y.imag};
}

static inline spy_Complex128
spy_operator$complex128_mul(spy_Complex128 x, spy_Complex128 y) {
    spy_Complex128 res;
    res.real = (x.real * y.real) - (x.imag * y.imag);
    res.imag = (x.real * y.imag) + (x.imag * y.real);
    return res;
}

static inline spy_Complex128
spy_operator$complex128_div(spy_Complex128 x, spy_Complex128 y) {
    double d = pow(y.real, 2.0) + pow(y.imag, 2.0);
    if (d == 0) {
        spy_panic("ZeroDivisionError", "complex division by zero", __FILE__, __LINE__);
    }
    spy_Complex128 res;
    res.real = ((x.real * y.real) + (x.imag * y.imag)) / d;
    res.imag = ((x.imag * y.real) - (x.real * y.imag)) / d;
    return res;
}

static inline bool
spy_operator$complex128_eq(spy_Complex128 x, spy_Complex128 y) {
    return (x.real == y.real) && (x.imag == y.imag);
}

static inline bool
spy_operator$complex128_ne(spy_Complex128 x, spy_Complex128 y) {
    return !((x.real == y.real) && (x.imag == y.imag));
}

static inline spy_Complex128
spy_operator$complex128_neg(spy_Complex128 x) {
    return (spy_Complex128){.real = -x.real, .imag = -x.imag};
}

#endif /* spy_complex_h */
