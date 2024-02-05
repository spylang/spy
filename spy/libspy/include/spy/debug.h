#ifndef SPY_DEBUG_H
#define SPY_DEBUG_H

#include "spy.h"

/***** WASM imports, must be provided by the host *****/
void spy_debug_log(const char *s);
void spy_debug_log_i32(const char *s, int32_t n);
void spy_debug_set_panic_message(const char *s);
/***** end of WASM imports *****/

static void inline spy_panic(const char *s) {
    spy_debug_log(s);
    spy_debug_set_panic_message(s);
    __builtin_trap();
}

#endif /* SPY_DEBUG_H */
