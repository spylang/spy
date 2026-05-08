#ifndef SPY___SPY___H
#define SPY___SPY___H

#include "spy/str.h"
#include <stdbool.h>
#include <stdio.h>

static inline bool
spy___spy__$is_compiled(void) {
    return true;
}

static inline void
spy___spy__$_stdio_write(spy_Str *s) {
    for (int32_t i = 0; i < s->length; i++)
        putchar(s->utf8[i]);
    putchar('\n');
}

#endif /* SPY___SPY___H */
