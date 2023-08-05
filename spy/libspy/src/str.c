#include "spy.h"

spy_Str *
spy_StrAlloc(size_t length) {
    size_t size = sizeof(spy_Str) + length;
    spy_Str *res = (spy_Str*)spy_GcAlloc(size).p;
    res->length = length;
    return res;
}

spy_Str *
spy_StrAdd(spy_Str *a, spy_Str *b) {
    size_t l = a->length + b->length;
    spy_Str *res = spy_StrAlloc(l);
    char *buf = (char*)res->utf8;
    memcpy(buf, a->utf8, a->length);
    memcpy(buf + a->length, b->utf8, b->length);
    return res;
}

spy_Str *
spy_StrMul(spy_Str *a, int32_t b) {
    size_t l = a->length * b;
    spy_Str *res = spy_StrAlloc(l);
    char *buf = (char*)res->utf8;
    for(int i=0; i<b; i++) {
        memcpy(buf, a->utf8, a->length);
        buf += a->length;
    }
    return res;
}


spy_Str *
spy_StrGetItem(spy_Str *s, int32_t i) {
    // XXX this is wrong: it should return a code point
    size_t l = s->length;
    if (i < 0) {
        i += l;
    }
    if (i >= l || i < 0) {
        spy_panic("string index out of bound");
        return NULL;
    }
    spy_Str *res = spy_StrAlloc(1);
    char *buf = (char*)res->utf8;
    buf[0] = s->utf8[i];
    return res;
}
