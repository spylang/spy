#ifndef SPY_DEBUG_H
#define SPY_DEBUG_H

#include "spy.h"

/* Debug utilities:
  - In emscripten and native mode, these are implemented in debug.c
  - In WASI mode, they must be provided by the host.

TODO: ideally, we want TWO different WASI modes:
  - for tests, we want the imports
  - for standalone executables, we want debug.c
*/
#ifdef SPY_TARGET_WASI
#  define IMP WASM_IMPORT
#else
#  define IMP(name) name
#endif

void IMP(spy_debug_log)(const char *s);
void IMP(spy_debug_log_i32)(const char *s, int32_t n);
void IMP(spy_debug_set_panic_message)(const char *s);

static void inline spy_panic(const char *s) {
    spy_debug_log(s);
    spy_debug_set_panic_message(s);
    __builtin_trap();
}

#endif /* SPY_DEBUG_H */
