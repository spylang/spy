#include <stdio.h>
#include "spy.h"

int32_t
spy_builtins$abs(int32_t x) {
    if (x < 0)
        return -x;
    return x;
}

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

void spy_builtins$print_NoneType(void) {
    printf("None\n");
}

void spy_builtins$print_str(spy_Str *s) {
    // I'm sure there is a better way but I'm offline and can't search :)
    for(int i=0; i < s->length; i++)
        printf("%c", s->utf8[i]);
    printf("\n");
}

static inline
int32_t spy_builtins$hash_i8(int8_t x) {
    if (x == -1) {
        return 2;
    }
    return (int32_t)x;
}

static inline
int32_t spy_builtins$hash_i32(int32_t x) {
    if (x == -1) {
        return 2;
    }
    return x;
}

static inline
int32_t spy_builtins$hash_u8(uint8_t x) {
    return (int32_t)x;
}

static inline
int32_t spy_builtins$hash_bool(bool x) {
    if (x)
        return 1;
    else
        return 0;
}

void spy_flush(void) {
    fflush(stdout);
    fflush(stderr);
}
