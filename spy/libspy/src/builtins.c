#include "spy.h"
#include <stdio.h>

void
spy_flush(void) {
    fflush(stdout);
    fflush(stderr);
}
