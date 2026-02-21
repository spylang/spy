#include "spy.h"
#include <stdarg.h>
#include <stdio.h>

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
