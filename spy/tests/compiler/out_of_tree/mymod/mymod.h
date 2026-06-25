#ifndef MYMOD_H
#define MYMOD_H

#include <spy.h>
#include <stdint.h>

spy_StrObject *spy_mymod$get_name(void);

// Accepts a c_func_ptr[i32, i32] callback and calls it with x.
// The typedef in spy_structdefs.h expands to int32_t (*)(int32_t),
// so we declare the parameter with the raw function pointer type.
int32_t spy_mymod$run_callback(int32_t (*cb)(int32_t), int32_t x);

#endif /* MYMOD_H */
