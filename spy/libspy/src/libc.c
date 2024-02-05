#include "spy.h"

int memcmp(const void *s1, const void *s2, size_t n) {
    // it seems that __builtin_memcmp simply calls libc's memcmp (which we
    // don't have), so we need to implement it by ourselves. Poor's man
    // implementation here :(
    const unsigned char *b1 = s1;
    const unsigned char *b2 = s2;

    for (size_t i = 0; i < n; ++i) {
        if (b1[i] < b2[i]) {
            return -1;
        } else if (b1[i] > b2[i]) {
            return 1;
        }
    }
    return 0;
}
