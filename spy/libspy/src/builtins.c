#include "spy.h"

int32_t
spy_builtins$abs(int32_t x) {
    if (x < 0)
        return -x;
    return x;
}

#ifdef SPY_NATIVE
#include <stdio.h>

void spy_builtins$print_i32(int32_t x) {
    printf("%d\n", x);
}

void spy_builtins$print_str(spy_Str *s) {
    printf("print_str not implemented\n");
}
#endif
