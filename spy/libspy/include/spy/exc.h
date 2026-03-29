#ifndef SPY_EXC_H
#define SPY_EXC_H

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

// All SPy exception types share the same C layout.
typedef struct {
    const char *message;
} spy_Exception;

#define SPY_EXC_MAX_FRAMES 64

typedef struct {
    const char *fqn;
    const char *filename;
    int32_t line;
    int32_t col_start;
    int32_t col_end;
} spy_FrameEntry;

typedef struct {
    // Null-terminated array of type names from most-specific to base, e.g.
    // {"ValueError", "Exception", NULL}.  NULL when no exception is set.
    const char * const *etype_chain;
    const char *message;
    const char *fname;
    int32_t lineno;
    int32_t nframes;
    spy_FrameEntry frames[SPY_EXC_MAX_FRAMES];
} spy_Exc;

extern spy_Exc SPY_exc;

static inline bool
spy_exc_is_set(void) {
    return SPY_exc.etype_chain != NULL;
}

void spy_exc_set(
    const char * const *etype_chain,
    const char *message,
    const char *fname,
    int32_t lineno
);
void spy_exc_clear(void);
bool spy_exc_matches(const char *etype);
void spy_exc_push_frame(
    const char *fqn,
    const char *filename,
    int32_t line,
    int32_t col_start,
    int32_t col_end
);

// Build a spy_Exception value from the currently-set exception (etype already
// consumed by the handler check).  Call after spy_exc_clear().
static inline spy_Exception
spy_exc_make(const char *message) {
    spy_Exception e;
    e.message = message;
    return e;
}

// WASM-exported helpers for reading exception state from the host.
int32_t spy_exc_get_etype(void);
int32_t spy_exc_get_message(void);
int32_t spy_exc_get_fname(void);
int32_t spy_exc_get_lineno(void);
int32_t spy_exc_get_nframes(void);
int32_t spy_exc_get_frame_fqn(int32_t i);
int32_t spy_exc_get_frame_filename(int32_t i);
int32_t spy_exc_get_frame_line(int32_t i);
int32_t spy_exc_get_frame_col_start(int32_t i);
int32_t spy_exc_get_frame_col_end(int32_t i);

#endif /* SPY_EXC_H */
