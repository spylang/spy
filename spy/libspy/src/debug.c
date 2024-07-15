#include "spy.h"
#include <stdio.h>
#include <stdint.h>

#if !defined(SPY_TARGET_WASI)

void spy_debug_log(const char *s) {
    printf("%s\n", s);
}

void spy_debug_log_i32(const char *s, int32_t n) {
    printf("%s %d\n", s, n);
}

void spy_debug_set_panic_message(const char *s) {
    printf("PANIC: %s\n", s);
}

#endif /* !defined(SPY_TARGET_WASI) */
