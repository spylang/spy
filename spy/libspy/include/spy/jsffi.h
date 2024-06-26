#ifndef SPY_JSFFI_H
#define SPY_JSFFI_H

#include <stddef.h>
#include "spy.h"

typedef struct {
    int id;
} JsRef;

JsRef jsffi_debug(const char *ptr);

static void spy_jsffi$debug(spy_Str *s) {
    jsffi_debug(s->utf8);
}

#endif /* SPY_JSFFI_H */
