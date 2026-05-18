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
spy___spy__$_stdout_write(spy_StrObject *s) {
    for (size_t i = 0; i < s->length; i++)
        putchar(s->utf8[i]);
}

#endif /* SPY___SPY___H */
