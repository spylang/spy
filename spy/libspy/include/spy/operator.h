#ifndef SPY_OPERATOR_H
#define SPY_OPERATOR_H

#include "spy.h"
#include "spy/debug.h"

static inline int32_t spy_operator$f64_to_i32(double x) { return x; }
static inline double spy_operator$i32_to_f64(int32_t x) { return x; }
static inline bool spy_operator$i32_to_bool(int32_t x) { return x; }

static inline void spy_operator$panic(spy_Str *s) {
    spy_panic(s->utf8);
}

#endif /* SPY_OPERATOR_H */
