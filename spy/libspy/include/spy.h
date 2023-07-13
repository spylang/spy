#ifndef SPY_H
#define SPY_H

#include <stdint.h>

typedef __SIZE_TYPE__ size_t;

// these are defied in walloc.c
void *malloc(size_t size);
void free(void *p);


#endif /* SPY_H */
