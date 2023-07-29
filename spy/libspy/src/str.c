#include "spy.h"

spy_StrObject
spy_StrAdd(spy_StrObject a, spy_StrObject b) {
    size_t l = a.length + b.length;
    char *buf = spy_GcAlloc(l).p;
    memcpy(buf, a.utf8_bytes, a.length);
    memcpy(buf+a.length, b.utf8_bytes, b.length);
    return spy_StrMake(l, buf);
}
