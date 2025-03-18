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


#ifdef SPY_TARGET_WASI

// for WASI/reactor targets, we expect the host to provide
// spy_debug_set_panic_message
void IMP(spy_debug_set_panic_message)
     (const char *s, const char *fname, int32_t lineno);

static void inline spy_panic(const char *s, const char *fname, int32_t lineno) {
    spy_debug_log(s);
    spy_debug_set_panic_message(s, fname, lineno);
    __builtin_trap();
}

#else

// for other targets, we define spy_panic in debug.c
void spy_panic(const char *s, const char *fname, int32_t lineno);

#endif


#endif /* SPY_DEBUG_H */
