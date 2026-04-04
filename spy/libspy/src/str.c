#include "spy.h"
#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>

spy_Str *
spy_str_alloc(size_t length) {
    size_t size = sizeof(spy_Str) + length;
    spy_Str *res = (spy_Str *)spy_GcAlloc(size).p;
    res->length = length;
    res->hash = 0;
    return res;
}

spy_Str *
spy_str_add(spy_Str *a, spy_Str *b) {
    size_t l = a->length + b->length;
    spy_Str *res = spy_str_alloc(l);
    char *buf = (char *)res->utf8;
    memcpy(buf, a->utf8, a->length);
    memcpy(buf + a->length, b->utf8, b->length);
    return res;
}

spy_Str *
spy_str_replace(spy_Str *original, spy_Str *old, spy_Str *new_str) {
    size_t orig_len = original->length;
    size_t old_len = old->length;
    size_t new_len = new_str->length;

    if (old_len == 0) {
        // when old_len is empty insert new_str before each byte and after the last
        size_t result_len = orig_len + (orig_len + 1) * new_len;
        spy_Str *res = spy_str_alloc(result_len);
        char *buf = (char *)res->utf8;
        for (size_t i = 0; i < orig_len; i++) {
            memcpy(buf, new_str->utf8, new_len);
            buf += new_len;
            buf[0] = original->utf8[i];
            buf++;
        }
        memcpy(buf, new_str->utf8, new_len);
        return res;
    }

    // First pass -> count occurrences
    size_t count = 0;
    const char *p = (const char *)original->utf8;
    const char *end = p + orig_len;
    while (p <= end - old_len) {
        if (memcmp(p, old->utf8, old_len) == 0) {
            count++;
            p += old_len;
        } else {
            p++;
        }
    }

    if (count == 0) {
        // Return the original string when no occurrences are found
        spy_Str *res = spy_str_alloc(orig_len);
        memcpy((char *)res->utf8, original->utf8, orig_len);
        return res;
    }

    // Second pass -> build the result
    size_t result_len = orig_len + count * (new_len - old_len);
    spy_Str *res = spy_str_alloc(result_len);
    char *buf = (char *)res->utf8;
    p = (const char *)original->utf8;
    while (p <= end - old_len) {
        if (memcmp(p, old->utf8, old_len) == 0) {
            memcpy(buf, new_str->utf8, new_len);
            buf += new_len;
            p += old_len;
        } else {
            *buf++ = *p++;
        }
    }
    // Copy remaining bytes
    size_t remaining = end - p;
    memcpy(buf, p, remaining);
    return res;
}

spy_Str *
spy_str_mul(spy_Str *a, int32_t b) {
    size_t l = a->length * b;
    spy_Str *res = spy_str_alloc(l);
    char *buf = (char *)res->utf8;
    for (int i = 0; i < b; i++) {
        memcpy(buf, a->utf8, a->length);
        buf += a->length;
    }
    return res;
}

bool
spy_str_eq(spy_Str *a, spy_Str *b) {
    if (a->length != b->length)
        return false;
    return memcmp(a->utf8, b->utf8, a->length) == 0;
}

spy_Str *
spy_str_getitem(spy_Str *s, int32_t i) {
    // XXX this is wrong: it should return a code point
    size_t l = s->length;
    if (i < 0) {
        i += l;
    }
    if (i >= l || i < 0) {
        spy_panic("IndexError", "string index out of bound", __FILE__, __LINE__);
        return NULL;
    }
    spy_Str *res = spy_str_alloc(1);
    char *buf = (char *)res->utf8;
    buf[0] = s->utf8[i];
    return res;
}

int32_t
spy_str_len(spy_Str *s) {
    return (int32_t)s->length;
}

spy_Str *
spy_str_repr(spy_Str *s) {
    // Choose quote character: use double quotes if string contains ' but not "
    char quote = '\'';
    for (size_t i = 0; i < s->length; i++) {
        if (s->utf8[i] == '\'') { quote = '"'; }
        if (s->utf8[i] == '"')  { quote = '\''; break; }
    }

    // First pass: calculate the output length
    size_t out_len = 2; // for the surrounding quotes
    for (size_t i = 0; i < s->length; i++) {
        unsigned char c = (unsigned char)s->utf8[i];
        if (c == '\\' || c == quote) {
            out_len += 2;
        } else if (c == '\n' || c == '\r' || c == '\t') {
            out_len += 2;
        } else if (c < 0x20) {
            out_len += 4; // \xNN
        } else {
            out_len += 1;
        }
    }

    // Second pass: fill the buffer
    spy_Str *res = spy_str_alloc(out_len);
    char *buf = (char *)res->utf8;
    *buf++ = quote;
    for (size_t i = 0; i < s->length; i++) {
        unsigned char c = (unsigned char)s->utf8[i];
        if (c == '\\') {
            *buf++ = '\\'; *buf++ = '\\';
        } else if (c == quote) {
            *buf++ = '\\'; *buf++ = quote;
        } else if (c == '\n') {
            *buf++ = '\\'; *buf++ = 'n';
        } else if (c == '\r') {
            *buf++ = '\\'; *buf++ = 'r';
        } else if (c == '\t') {
            *buf++ = '\\'; *buf++ = 't';
        } else if (c < 0x20) {
            buf += sprintf(buf, "\\x%02x", c);
        } else {
            *buf++ = c;
        }
    }
    *buf++ = quote;
    return res;
}

int32_t
spy_str_hash(spy_Str *s) {
    if (s->hash != 0)
        return s->hash;
    // FNV-1a hash
    uint32_t h = 2166136261u;
    for (size_t i = 0; i < s->length; i++) {
        h ^= (uint8_t)s->utf8[i];
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

// Helper function to format and convert to spy_Str
// XXX probably it would be better to implement it directly, instead of
// bringing in all the code needed to support sprintf()
static spy_Str *
spy_str_from_format(const char *fmt, ...) {
    char buf[1024];
    va_list args;
    va_start(args, fmt);
    int length = vsnprintf(buf, 1024, fmt, args);
    va_end(args);

    spy_Str *res = spy_str_alloc(length);
    char *outbuf = (char *)res->utf8;
    memcpy(outbuf, buf, length);
    return res;
}

spy_Str *
spy_builtins$i32$__str__(int32_t x) {
    return spy_str_from_format("%d", x);
}

spy_Str *
spy_builtins$i8$__str__(int8_t x) {
    return spy_str_from_format("%d", (int)x);
}

spy_Str *
spy_builtins$u8$__str__(uint8_t x) {
    return spy_str_from_format("%u", (unsigned int)x);
}

spy_Str *
spy_builtins$f64$__str__(double x) {
    return spy_str_from_format("%g", x);
}

spy_Str *
spy_builtins$bool$__str__(bool x) {
    return spy_str_from_format("%s", x ? "True" : "False");
}

// Helper: parse a null-terminated copy of spy_Str as an int64_t, raising
// ValueError if the string is not a valid integer.
static int64_t
spy_str_parse_i64(spy_Str *s) {
    // spy_Str is not null-terminated, so we copy it
    char buf[64];
    size_t len = s->length;
    if (len >= sizeof(buf)) {
        spy_panic(
            "ValueError", "invalid literal for int() with base 10", __FILE__, __LINE__
        );
    }
    memcpy(buf, s->utf8, len);
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
spy_operator$str_to_i32(spy_Str *s) {
    int64_t val = spy_str_parse_i64(s);
    spy_check_range(val, -2147483648LL, 2147483647LL, "i32");
    return (int32_t)val;
}

uint32_t
spy_operator$str_to_u32(spy_Str *s) {
    int64_t val = spy_str_parse_i64(s);
    spy_check_range(val, 0LL, 4294967295LL, "u32");
    return (uint32_t)val;
}

int8_t
spy_operator$str_to_i8(spy_Str *s) {
    int64_t val = spy_str_parse_i64(s);
    spy_check_range(val, -128LL, 127LL, "i8");
    return (int8_t)val;
}

uint8_t
spy_operator$str_to_u8(spy_Str *s) {
    int64_t val = spy_str_parse_i64(s);
    spy_check_range(val, 0LL, 255LL, "u8");
    return (uint8_t)val;
}

spy_Complex128
spy_str_to_complex128(spy_Str *s) {
    char buf[128];
    size_t len = s->length;
    if (len == 0 || len >= sizeof(buf)) {
        spy_panic(
            "ValueError", "complex() arg is a malformed string", __FILE__, __LINE__
        );
    }

    memcpy(buf, s->utf8, len);
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
