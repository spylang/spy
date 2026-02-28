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

spy_StringBuilder *
spy_str_builder_new(int32_t initial_capacity) {
    spy_StringBuilder *sb =
        (spy_StringBuilder *)spy_GcAlloc(sizeof(spy_StringBuilder)).p;
    sb->length = 0;
    sb->capacity = (size_t)initial_capacity;
    sb->buf = (char *)malloc((size_t)initial_capacity);
    return sb;
}

spy_StringBuilder *
spy_str_builder_push(spy_StringBuilder *sb, spy_Str *s) {
    size_t needed = sb->length + s->length;
    if (needed > sb->capacity) {
        size_t new_cap = sb->capacity * 2;
        while (new_cap < needed)
            new_cap *= 2;
        sb->buf = (char *)realloc(sb->buf, new_cap);
        sb->capacity = new_cap;
    }
    memcpy(sb->buf + sb->length, s->utf8, s->length);
    sb->length += s->length;
    return sb;
}

spy_Str *
spy_str_builder_build(spy_StringBuilder *sb) {
    spy_Str *res = spy_str_alloc(sb->length);
    memcpy((char *)res->utf8, sb->buf, sb->length);
    return res;
}
