#include <stdio.h>
#include "spy.h"

spy_Str *
spy_str_alloc(size_t length) {
    size_t size = sizeof(spy_Str) + length;
    spy_Str *res = (spy_Str*)spy_GcAlloc(size).p;
    res->length = length;
    return res;
}

spy_Str *
spy_str_add(spy_Str *a, spy_Str *b) {
    size_t l = a->length + b->length;
    spy_Str *res = spy_str_alloc(l);
    char *buf = (char*)res->utf8;
    memcpy(buf, a->utf8, a->length);
    memcpy(buf + a->length, b->utf8, b->length);
    return res;
}

spy_Str *
spy_str_mul(spy_Str *a, int32_t b) {
    size_t l = a->length * b;
    spy_Str *res = spy_str_alloc(l);
    char *buf = (char*)res->utf8;
    for(int i=0; i<b; i++) {
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
        spy_panic("IndexError", "string index out of bound",
                  __FILE__, __LINE__);
        return NULL;
    }
    spy_Str *res = spy_str_alloc(1);
    char *buf = (char*)res->utf8;
    buf[0] = s->utf8[i];
    return res;
}

int32_t
spy_str_len(spy_Str *s) {
    return (int32_t)s->length;
}

// XXX probably it would be better to implement it directly, instead of
// bringing in all the code needed to support sprintf()
spy_Str *
spy_builtins$int2str(int32_t x) {
    char buf[1024];
    snprintf(buf, 1024, "%d", x);
    size_t length = strlen(buf);

    spy_Str *res = spy_str_alloc(length);
    char *outbuf = (char*)res->utf8;
    memcpy(outbuf, buf, length);
    return res;
}

spy_Str *
spy_builtins$float2str(double x) {
    char buf[1024];
    snprintf(buf, 1024, "%g", x);
    size_t length = strlen(buf);

    spy_Str *res = spy_str_alloc(length);
    char *outbuf = (char*)res->utf8;
    memcpy(outbuf, buf, length);
    return res;
}
