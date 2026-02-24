#ifndef SPY_COMPLEX_H
#  define SPY_COMPLEX_H

#  include "spy.h"
#  include "spy/debug.h"
#  include <complex.h>
#  include <math.h>

typedef struct {
    double real;
    double imag;
} spy_Complex128;
#endif /* SPY_COMPLEX_H */

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
    x.real = -x.real;
    x.imag = -x.imag;
    return x;
}
