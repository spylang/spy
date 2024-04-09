#include "spy.h"

int32_t
spy_builtins$abs(int32_t x) {
    if (x < 0)
        return -x;
    return x;
}
