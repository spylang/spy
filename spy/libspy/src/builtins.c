#include "spy.h"
#include <stdio.h>

int32_t
spy_builtins$min(int32_t x, int32_t y) {
    if (x < y)
        return x;
    return y;
}

int32_t
spy_builtins$max(int32_t x, int32_t y) {
    if (x > y)
        return x;
    return y;
}

void
spy_flush(void) {
    fflush(stdout);
    fflush(stderr);
}
