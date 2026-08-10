#ifndef SPY_DEBUG_H
#define SPY_DEBUG_H

#include "spy.h"

/* Debug utilities:
  - for testlib, they must be provided by the host: this is what we want for
    tests, where the host records the panic and turns it into a SPyError.
  - in all the other cases, they are implemented in debug.c.
*/
#ifdef SPY_OUTPUT_KIND_TESTLIB
#  define SPY_DEBUG_FROM_HOST
#endif

#ifdef SPY_DEBUG_FROM_HOST

// the host provides these as WASM imports. On emscripten the linker also wants
// a JS definition for them: see the EMSCRIPTEN_IMPORT stubs in debug.c
void WASM_IMPORT(spy_debug_log)(const char *s);
void WASM_IMPORT(spy_debug_log_i32)(const char *s, int32_t n);
void WASM_IMPORT(spy_debug_set_panic_message)(
    const char *etype,
    const char *message,
    const char *fname,
    int32_t lineno
);

static void inline spy_panic(
    const char *etype,
    const char *message,
    const char *fname,
    int32_t lineno
) {
    spy_debug_log(etype);
    spy_debug_log(message);
    spy_debug_set_panic_message(etype, message, fname, lineno);
    __builtin_trap();
}

#else

void spy_debug_log(const char *s);
void spy_debug_log_i32(const char *s, int32_t n);

// in all the other cases, we define spy_panic in debug.c
NORETURN
void
spy_panic(const char *etype, const char *message, const char *fname, int32_t lineno);

#endif

#endif /* SPY_DEBUG_H */
