#include "spy.h"
#include <stddef.h>
#include <stdio.h>

_spy_BytesObject_Layout
_spy_BytesObject_layout(void) {
    return (_spy_BytesObject_Layout){
        .size = sizeof(spy_BytesObject),
        .length_offset = offsetof(spy_BytesObject, length),
        .hash_offset = offsetof(spy_BytesObject, hash),
        .data_offset = offsetof(spy_BytesObject, data),
    };
}

spy_BytesObject *
spy_bytes_alloc(size_t length) {
    // allocate a spy_BytesObject AND the data buffer as a single allocation
    size_t size = sizeof(spy_BytesObject) + length;
    spy_BytesObject *res = (spy_BytesObject *)spy_GcAlloc(size).p;
    res->length = length;
    res->hash = 0;
#ifdef SPY_DEBUG
    res->data = (spy_gc_ptr_u8){(uint8_t *)(res + 1), (ptrdiff_t)length};
#else
    res->data = (spy_gc_ptr_u8){(uint8_t *)(res + 1)};
#endif
    return res;
}

spy_BytesObject *
spy_bytes_add(spy_BytesObject *a, spy_BytesObject *b) {
    size_t l = a->length + b->length;
    spy_BytesObject *res = spy_bytes_alloc(l);
    uint8_t *buf = spy_BytesObject_DATA(res);
    memcpy(buf, spy_BytesObject_DATA(a), a->length);
    memcpy(buf + a->length, spy_BytesObject_DATA(b), b->length);
    return res;
}

spy_BytesObject *
spy_bytes_mul(spy_BytesObject *a, int32_t b) {
    size_t l = a->length * b;
    spy_BytesObject *res = spy_bytes_alloc(l);
    uint8_t *buf = spy_BytesObject_DATA(res);
    for (int i = 0; i < b; i++) {
        memcpy(buf, spy_BytesObject_DATA(a), a->length);
        buf += a->length;
    }
    return res;
}

bool
spy_bytes_eq(spy_BytesObject *a, spy_BytesObject *b) {
    if (a->length != b->length)
        return false;
    return memcmp(spy_BytesObject_DATA(a), spy_BytesObject_DATA(b), a->length) == 0;
}

uint8_t
spy_bytes_getitem(spy_BytesObject *b, int32_t i) {
    size_t l = b->length;
    if (i < 0) {
        i += l;
    }
    if (i >= (int32_t)l || i < 0) {
        spy_panic("IndexError", "bytes index out of range", __FILE__, __LINE__);
        return 0;
    }
    return spy_BytesObject_DATA(b)[i];
}

int32_t
spy_bytes_len(spy_BytesObject *b) {
    return (int32_t)b->length;
}

spy_StrObject *
spy_bytes_repr(spy_BytesObject *b) {
    // First pass: calculate the output length (b'...' format)
    size_t out_len = 3; // b + quote + quote
    for (size_t i = 0; i < b->length; i++) {
        uint8_t c = spy_BytesObject_DATA(b)[i];
        if (c == '\\' || c == '\'') {
            out_len += 2;
        } else if (c == '\n' || c == '\r' || c == '\t') {
            out_len += 2;
        } else if (c < 0x20 || c >= 0x80) {
            out_len += 4; // \xNN
        } else {
            out_len += 1;
        }
    }

    // Second pass: fill the buffer
    spy_StrObject *res = spy_str_alloc(out_len);
    char *buf = (char *)spy_StrObject_UTF8(res);
    *buf++ = 'b';
    *buf++ = '\'';
    for (size_t i = 0; i < b->length; i++) {
        uint8_t c = spy_BytesObject_DATA(b)[i];
        if (c == '\\') {
            *buf++ = '\\';
            *buf++ = '\\';
        } else if (c == '\'') {
            *buf++ = '\\';
            *buf++ = '\'';
        } else if (c == '\n') {
            *buf++ = '\\';
            *buf++ = 'n';
        } else if (c == '\r') {
            *buf++ = '\\';
            *buf++ = 'r';
        } else if (c == '\t') {
            *buf++ = '\\';
            *buf++ = 't';
        } else if (c < 0x20 || c >= 0x80) {
            buf += sprintf(buf, "\\x%02x", c);
        } else {
            *buf++ = (char)c;
        }
    }
    *buf++ = '\'';
    return res;
}

int32_t
spy_bytes_hash(spy_BytesObject *b) {
    if (b->hash != 0)
        return b->hash;
    // FNV-1a hash (same algorithm as str, hashes intentionally not required to match)
    uint32_t h = 2166136261u;
    for (size_t i = 0; i < b->length; i++) {
        h ^= spy_BytesObject_DATA(b)[i];
        h *= 16777619u;
    }
    int32_t result = (int32_t)h;
    if (result == -1)
        result = -2;
    if (result == 0)
        result = 1;
    b->hash = result;
    return result;
}
