#include "spy.h"

int32_t
spy_builtins__abs(int32_t x) {
    if (x < 0)
        return -x;
    return x;
}

int32_t
spy_testmod__double(int32_t x) {
    return x*2;
}
