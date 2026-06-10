#include "spy.h"
#include <errno.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>

_spy_StrObject_Layout
_spy_StrObject_layout(void) {
    return (_spy_StrObject_Layout){
        .size = sizeof(spy_StrObject),
        .length_offset = offsetof(spy_StrObject, length),
        .hash_offset = offsetof(spy_StrObject, hash),
        .utf8_offset = offsetof(spy_StrObject, utf8),
    };
}

spy_StrObject *
spy_str_alloc(size_t length) {
    // allocate a spy_StrObject AND the utf8 buffer as a single allocation
    size_t size = sizeof(spy_StrObject) + length;
    spy_StrObject *res = (spy_StrObject *)spy_GcAlloc(size).p;
    res->length = length;
    res->hash = 0;
#ifdef SPY_DEBUG
    res->utf8 = (spy_gc_ptr_u8){(uint8_t *)(res + 1), (ptrdiff_t)length};
#else
    res->utf8 = (spy_gc_ptr_u8){(uint8_t *)(res + 1)};
#endif
    return res;
}

bool
spy_str_eq(spy_StrObject *a, spy_StrObject *b) {
    if (a->length != b->length)
        return false;
    return memcmp(spy_StrObject_UTF8(a), spy_StrObject_UTF8(b), a->length) == 0;
}

int32_t
spy_str_hash(spy_StrObject *s) {
    if (s->hash != 0)
        return s->hash;
    // FNV-1a hash
    uint32_t h = 2166136261u;
    for (size_t i = 0; i < s->length; i++) {
        h ^= (uint8_t)spy_StrObject_UTF8(s)[i];
        h *= 16777619u;
    }
    int32_t result = (int32_t)h;
    if (result == -1)
        result = -2;
    if (result == 0)
        result = 1;
    s->hash = result;
    return result;
}

// Helper function to format and convert to spy_StrObject
// XXX probably it would be better to implement it directly, instead of
// bringing in all the code needed to support sprintf()
static spy_StrObject *
spy_str_from_format(const char *fmt, ...) {
    char buf[1024];
    va_list args;
    va_start(args, fmt);
    int length = vsnprintf(buf, 1024, fmt, args);
    va_end(args);

    spy_StrObject *res = spy_str_alloc(length);
    char *outbuf = (char *)spy_StrObject_UTF8(res);
    memcpy(outbuf, buf, length);
    return res;
}

spy_StrObject *
spy_builtins$i32$__str__(int32_t x) {
    return spy_str_from_format("%d", x);
}

spy_StrObject *
spy_builtins$i64$__str__(int64_t x) {
    return spy_str_from_format("%lld", (long long)x);
}

spy_StrObject *
spy_builtins$u64$__str__(uint64_t x) {
    return spy_str_from_format("%llu", (unsigned long long)x);
}

spy_StrObject *
spy_builtins$i8$__str__(int8_t x) {
    return spy_str_from_format("%d", (int)x);
}

spy_StrObject *
spy_builtins$u8$__str__(uint8_t x) {
    return spy_str_from_format("%u", (unsigned int)x);
}

spy_StrObject *
spy_builtins$f64$__str__(double x) {
    return spy_str_from_format("%g", x);
}

spy_StrObject *
spy_builtins$bool$__str__(bool x) {
    return spy_str_from_format("%s", x ? "True" : "False");
}

// Helper: parse a null-terminated copy of spy_StrObject as an int64_t, raising
// ValueError if the string is not a valid integer.
static int64_t
spy_str_parse_i64(spy_StrObject *s) {
    // spy_StrObject is not null-terminated, so we copy it
    char buf[64];
    size_t len = s->length;
    if (len >= sizeof(buf)) {
        spy_panic(
            "ValueError", "invalid literal for int() with base 10", __FILE__, __LINE__
        );
    }
    memcpy(buf, spy_StrObject_UTF8(s), len);
    buf[len] = '\0';

    char *end;
    errno = 0;
    int64_t val = strtoll(buf, &end, 10);
    if (end == buf || *end != '\0' || errno != 0) {
        char msg[128];
        snprintf(msg, sizeof(msg), "invalid literal for int() with base 10: '%s'", buf);
        spy_panic("ValueError", msg, __FILE__, __LINE__);
    }
    return val;
}

static void
spy_check_range(int64_t val, int64_t lo, int64_t hi, const char *tname) {
    if (val < lo || val > hi) {
        char msg[128];
        snprintf(
            msg, sizeof(msg), "%s value %lld out of range [%lld, %lld]", tname,
            (long long)val, (long long)lo, (long long)hi
        );
        spy_panic("OverflowError", msg, __FILE__, __LINE__);
    }
}

int32_t
spy_operator$str_to_i32(spy_StrObject *s) {
    int64_t val = spy_str_parse_i64(s);
    spy_check_range(val, -2147483648LL, 2147483647LL, "i32");
    return (int32_t)val;
}

uint32_t
spy_operator$str_to_u32(spy_StrObject *s) {
    int64_t val = spy_str_parse_i64(s);
    spy_check_range(val, 0LL, 4294967295LL, "u32");
    return (uint32_t)val;
}

int64_t
spy_operator$str_to_i64(spy_StrObject *s) {
    // We can't reuse spy_str_parse_i64: it reports overflow as a ValueError,
    // but for an explicit i64() conversion an out-of-range value must be an
    // OverflowError (matching the interp path and the other int types).
    char buf[64];
    size_t len = s->length;
    if (len >= sizeof(buf)) {
        spy_panic(
            "ValueError", "invalid literal for int() with base 10", __FILE__, __LINE__
        );
    }
    memcpy(buf, spy_StrObject_UTF8(s), len);
    buf[len] = '\0';

    char *end;
    errno = 0;
    long long val = strtoll(buf, &end, 10);
    if (end == buf || *end != '\0') {
        char msg[128];
        snprintf(msg, sizeof(msg), "invalid literal for int() with base 10: '%s'", buf);
        spy_panic("ValueError", msg, __FILE__, __LINE__);
    }
    if (errno != 0) {
        char msg[256];
        snprintf(
            msg, sizeof(msg),
            "i64 value %s out of range [-9223372036854775808, 9223372036854775807]",
            buf
        );
        spy_panic("OverflowError", msg, __FILE__, __LINE__);
    }
    return (int64_t)val;
}

uint64_t
spy_operator$str_to_u64(spy_StrObject *s) {
    // u64's max exceeds int64, so we can't reuse spy_str_parse_i64. strtoull
    // would silently wrap a leading '-' into a huge positive value, so we
    // reject negatives explicitly to match Python's int() + range semantics.
    char buf[64];
    size_t len = s->length;
    if (len >= sizeof(buf)) {
        spy_panic(
            "ValueError", "invalid literal for int() with base 10", __FILE__, __LINE__
        );
    }
    memcpy(buf, spy_StrObject_UTF8(s), len);
    buf[len] = '\0';

    char *end;
    errno = 0;
    unsigned long long val = strtoull(buf, &end, 10);
    if (end == buf || *end != '\0') {
        char msg[128];
        snprintf(msg, sizeof(msg), "invalid literal for int() with base 10: '%s'", buf);
        spy_panic("ValueError", msg, __FILE__, __LINE__);
    }
    if (errno != 0 || strchr(buf, '-') != NULL) {
        char msg[256];
        snprintf(
            msg, sizeof(msg),
            "u64 value %s out of range [0, 18446744073709551615]", buf
        );
        spy_panic("OverflowError", msg, __FILE__, __LINE__);
    }
    return (uint64_t)val;
}

int8_t
spy_operator$str_to_i8(spy_StrObject *s) {
    int64_t val = spy_str_parse_i64(s);
    spy_check_range(val, -128LL, 127LL, "i8");
    return (int8_t)val;
}

uint8_t
spy_operator$str_to_u8(spy_StrObject *s) {
    int64_t val = spy_str_parse_i64(s);
    spy_check_range(val, 0LL, 255LL, "u8");
    return (uint8_t)val;
}

spy_Complex128
spy_str_to_complex128(spy_StrObject *s) {
    char buf[128];
    size_t len = s->length;
    if (len == 0 || len >= sizeof(buf)) {
        spy_panic(
            "ValueError", "complex() arg is a malformed string", __FILE__, __LINE__
        );
    }

    memcpy(buf, spy_StrObject_UTF8(s), len);
    buf[len] = '\0';
    char *start = buf;
    char *end = start + len - 1;

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
