#ifndef SPY_POSIX_H
#define SPY_POSIX_H

#include <stdio.h>

#ifndef SPY_TARGET_WASI
#  include <sys/ioctl.h>
#endif
#include <unistd.h>

FILE *WASM_EXPORT(spy_posix$_fopen)(spy_Str *filename, spy_Str *mode);
spy_Str *WASM_EXPORT(spy_posix$_fread)(FILE *f, int32_t size);
spy_Str *WASM_EXPORT(spy_posix$__freadall_chunked)(FILE *f);
spy_Str *WASM_EXPORT(spy_posix$_freadall)(FILE *f);
spy_Str *WASM_EXPORT(spy_posix$_freadline)(FILE *f);
int32_t WASM_EXPORT(spy_posix$_ftell)(FILE *f);
void WASM_EXPORT(spy_posix$_fseek)(FILE *f, int32_t offset, int32_t whence);
void WASM_EXPORT(spy_posix$_fwrite)(FILE *f, spy_Str *data);
void WASM_EXPORT(spy_posix$_fflush)(FILE *f);
int32_t WASM_EXPORT(spy_posix$_fileno)(FILE *f);
bool WASM_EXPORT(spy_posix$_isatty)(int32_t fd);
void WASM_EXPORT(spy_posix$_fclose)(FILE *f);

// NOTE: this struct is also defined in vm/modules/posix.py, the two definitions must be
// kept in sync
typedef struct spy_posix$TerminalSize spy_posix$TerminalSize;
struct spy_posix$TerminalSize {
    int32_t columns;
    int32_t lines;
};

static inline spy_posix$TerminalSize
spy_posix$get_terminal_size(void) {
    spy_posix$TerminalSize result;

#ifndef SPY_TARGET_WASI
    struct winsize w;
    if (ioctl(STDOUT_FILENO, TIOCGWINSZ, &w) == 0) {
        result.columns = w.ws_col;
        result.lines = w.ws_row;
    } else {
        result.columns = 80;
        result.lines = 24;
    }
#else
    // Fallback to default values on WASI (no terminal support)
    result.columns = 80;
    result.lines = 24;
#endif

    return result;
}

static inline bool
spy_posix$_FILE$__eq__(FILE *f0, FILE *f1) {
    return f0 == f1;
}

static inline bool
spy_posix$_FILE$__ne__(FILE *f0, FILE *f1) {
    return f0 != f1;
}

#endif /* SPY_POSIX_H */
