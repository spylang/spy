#include <stdio.h>
#include "spy.h"

int32_t
spy_builtins$abs(int32_t x) {
    if (x < 0)
        return -x;
    return x;
}


void spy_builtins$print_i32(int32_t x) {
    printf("%d\n", x);
}

void spy_builtins$print_f64(double x) {
    printf("%f\n", x);
}

void spy_builtins$print_bool(bool x) {
    if (x)
        printf("True\n");
    else
        printf("False\n");
}

void spy_builtins$print_void(void) {
    printf("None\n");
}

void spy_builtins$print_str(spy_Str *s) {
    // I'm sure there is a better way but I'm offline and can't search :)
    for(int i=0; i < s->length; i++)
        printf("%c", s->utf8[i]);
    printf("\n");
}

void spy_flush(void) {
    fflush(stdout);
    fflush(stderr);
}
