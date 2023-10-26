#include "spy.h"

int32_t
spy_abs(int32_t x) {
    if (x < 0)
        return -x;
    return x;
}

int32_t
spy_testmod_double(int32_t x) {
    return x*2;
}
