#ifndef SPY_STR_H
#define SPY_STR_H

#include <stddef.h>

typedef struct {
    size_t length;
    const char *utf8_bytes;
} spy_StrObject;


// just syntactic sugar because the syntax for struct literals is very ugly
static inline spy_StrObject
spy_StrMake(size_t length, const char *utf8_bytes) {
    return (spy_StrObject){length, utf8_bytes};
}

spy_StrObject spy_StrAdd(spy_StrObject a, spy_StrObject b);

#endif /* SPY_STR_H */
