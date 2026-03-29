#include "spy.h"
#include <string.h>

spy_Exc SPY_exc = {NULL, NULL, NULL, 0, 0, {{0}}};

void
spy_exc_set(
    const char * const *etype_chain,
    const char *message,
    const char *fname,
    int32_t lineno
) {
    SPY_exc.etype_chain = etype_chain;
    SPY_exc.message = message;
    SPY_exc.fname = fname;
    SPY_exc.lineno = lineno;
}

void WASM_EXPORT(spy_exc_clear)(void) {
    SPY_exc.etype_chain = NULL;
    SPY_exc.message = NULL;
    SPY_exc.fname = NULL;
    SPY_exc.lineno = 0;
    SPY_exc.nframes = 0;
}

bool
spy_exc_matches(const char *etype) {
    if (SPY_exc.etype_chain == NULL)
        return false;
    for (int i = 0; SPY_exc.etype_chain[i] != NULL; i++) {
        if (strcmp(SPY_exc.etype_chain[i], etype) == 0)
            return true;
    }
    return false;
}

void
spy_exc_push_frame(
    const char *fqn,
    const char *filename,
    int32_t line,
    int32_t col_start,
    int32_t col_end
) {
    if (SPY_exc.nframes >= SPY_EXC_MAX_FRAMES)
        return;
    int32_t i = SPY_exc.nframes++;
    SPY_exc.frames[i].fqn = fqn;
    SPY_exc.frames[i].filename = filename;
    SPY_exc.frames[i].line = line;
    SPY_exc.frames[i].col_start = col_start;
    SPY_exc.frames[i].col_end = col_end;
}

int32_t WASM_EXPORT(spy_exc_get_etype)(void) {
    if (SPY_exc.etype_chain == NULL)
        return 0;
    return (int32_t)(intptr_t)SPY_exc.etype_chain[0];
}

int32_t WASM_EXPORT(spy_exc_get_message)(void) {
    return (int32_t)(intptr_t)SPY_exc.message;
}

int32_t WASM_EXPORT(spy_exc_get_fname)(void) {
    return (int32_t)(intptr_t)SPY_exc.fname;
}

int32_t WASM_EXPORT(spy_exc_get_lineno)(void) {
    return SPY_exc.lineno;
}

int32_t WASM_EXPORT(spy_exc_get_nframes)(void) {
    return SPY_exc.nframes;
}

int32_t WASM_EXPORT(spy_exc_get_frame_fqn)(int32_t i) {
    return (int32_t)(intptr_t)SPY_exc.frames[i].fqn;
}

int32_t WASM_EXPORT(spy_exc_get_frame_filename)(int32_t i) {
    return (int32_t)(intptr_t)SPY_exc.frames[i].filename;
}

int32_t WASM_EXPORT(spy_exc_get_frame_line)(int32_t i) {
    return SPY_exc.frames[i].line;
}

int32_t WASM_EXPORT(spy_exc_get_frame_col_start)(int32_t i) {
    return SPY_exc.frames[i].col_start;
}

int32_t WASM_EXPORT(spy_exc_get_frame_col_end)(int32_t i) {
    return SPY_exc.frames[i].col_end;
}
