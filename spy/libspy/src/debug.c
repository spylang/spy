#include "spy.h"
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>

#if !defined(SPY_TARGET_WASI)

void spy_debug_log(const char *s) {
    printf("%s\n", s);
}

void spy_debug_log_i32(const char *s, int32_t n) {
    printf("%s %d\n", s, n);
}

void spy_panic(const char *s, const char *fname, int32_t lineno) {
    if (fname != NULL)
        fprintf(stderr, "%s at %s:%d\n", s, fname, lineno);
    else
        fprintf(stderr, "%s\n", s);
    abort();
}

#endif /* !defined(SPY_TARGET_WASI) */
