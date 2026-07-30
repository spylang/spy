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
#if defined(SPY_TARGET_WASI) || defined(SPY_TARGET_EMSCRIPTEN)
#  define IMP(name) WASM_IMPORT(name)
#else
#  define IMP(name) name
#endif

void IMP(spy_debug_log)(const char *s);
void IMP(spy_debug_log_i32)(const char *s, int32_t n);

NORETURN void spy_panic_helper(
    const char *etype,
    const char *message,
    const char *fname,
    int32_t lineno
);

#if defined(SPY_TARGET_WASI) || defined(SPY_TARGET_EMSCRIPTEN)

// for WASI/reactor targets, we expect the host to provide
// spy_debug_set_panic_message
void IMP(spy_debug_set_panic_message)(
    const char *etype,
    const char *message,
    const char *fname,
    int32_t lineno
);

int spy_debug_have_imports(void);

static int inline spy_panic(
    const char *etype,
    const char *message,
    const char *fname,
    int32_t lineno
) {
    if (spy_debug_have_imports()) {
        spy_debug_log(etype);
        spy_debug_log(message);
        spy_debug_set_panic_message(etype, message, fname, lineno);
        __builtin_trap();
    } else {
        spy_panic_helper(etype, message, fname, lineno);
    }
}

#else

static void inline spy_panic(
    const char *etype,
    const char *message,
    const char *fname,
    int32_t lineno
) {
    spy_panic_helper(etype, message, fname, lineno);
}

#endif

#endif /* SPY_DEBUG_H */
