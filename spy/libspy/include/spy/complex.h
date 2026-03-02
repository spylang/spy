#ifndef SPY_COMPLEX_H
#define SPY_COMPLEX_H

#include "spy.h"
#include "spy/debug.h"
#include "spy/str.h"
#include <complex.h>
#include <ctype.h>
#include <errno.h>
#include <math.h>

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
    x.imag = -x.imag;
    return x;
}

spy_Complex128
spy_operator$str_to_complex128(spy_Str *x) {
    size_t len = x->length;
    if (len == 0) {
        spy_panic(
            "ValueError", "complex() arg is a malformed string", __FILE__, __LINE__
        );
    }

    char *start = spy_str_alloc(len)->utf8;
    const char *s = (char *)x->utf8;
    memcpy(start, s, len);
    char *end = start + len - 1;
    start[len] = '\0';

    while (isspace(*start))
        start++;
    while (end >= start && isspace(*end))
        end--;

    if (*start == '(') {
        if (*end != ')') {
            spy_panic(
                "ValueError", "complex() arg is a malformed string", __FILE__, __LINE__
            );
        }

        start++;
        end--;
    }

    while (isspace(*start))
        start++;
    while (end >= start && isspace(*end))
        end--;
    *(end + 1) = '\0';

    if (start >= end) {
        spy_panic(
            "ValueError", "complex() arg is a malformed string", __FILE__, __LINE__
        );
    }
    /* a valid complex string usually takes one of the three forms:

         <float>                  - real part only
         <float>j                 - imaginary part only
         <float><signed-float>j   - real and imaginary parts

       where <float> represents any numeric string that's accepted by the
       float constructor (including 'nan', 'inf', 'infinity', etc.), and
       <signed-float> is any string of the form <float> whose first
       character is '+' or '-'.
    */

    double real_val = 0.0;
    double imag_val = 0.0;

    char *floatEndPtr;
    double val = strtod(start, &floatEndPtr);
    if (floatEndPtr == start || errno == ERANGE) {
        spy_panic(
            "ValueError", "complex() arg is a malformed string", __FILE__, __LINE__
        );
    }

    // <float>
    real_val = val;

    if (*floatEndPtr) {
        if (*floatEndPtr == 'j' || *floatEndPtr == 'J') {
            // if imag part only, then should hit null terminator
            if (*(floatEndPtr + 1)) {
                spy_panic(
                    "ValueError", "complex() arg is a malformed string", __FILE__,
                    __LINE__
                );
            }

            // <float>j
            imag_val = val;
            real_val = 0.0;
        } else {
            // reject if any space between <float> <signed-float>j or
            // <float>\t\t<signed-float>j
            if (isspace(*floatEndPtr)) {
                spy_panic(
                    "ValueError", "complex() arg is a malformed string", __FILE__,
                    __LINE__
                );
            }

            start = floatEndPtr;
            val = strtod(start, &floatEndPtr);
            if (floatEndPtr == start || errno == ERANGE) {
                spy_panic(
                    "ValueError", "complex() arg is a malformed string", __FILE__,
                    __LINE__
                );
            }

            if (*floatEndPtr != 'j' && *floatEndPtr != 'J') {
                spy_panic(
                    "ValueError", "complex() arg is a malformed string", __FILE__,
                    __LINE__
                );
            }

            // <float><signed-float>j
            imag_val = val;
        }
    }

    return (spy_Complex128){.real = real_val, .imag = imag_val};
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
    x.real = -x.real;
    x.imag = -x.imag;
    return x;
}

#endif /* spy_complex_h */
