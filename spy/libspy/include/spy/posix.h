#ifndef SPY_POSIX_H
#define SPY_POSIX_H

#ifndef SPY_TARGET_WASI
#  include <sys/ioctl.h>
#endif
#include <unistd.h>

typedef struct {
    int32_t columns;
    int32_t lines;
} spy_TerminalSize;

static inline spy_TerminalSize
spy_posix$get_terminal_size(void) {
    spy_TerminalSize result;

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

static inline int32_t
spy_posix$TerminalSize$__get_columns__(spy_TerminalSize self) {
    return self.columns;
}

static inline int32_t
spy_posix$TerminalSize$__get_lines__(spy_TerminalSize self) {
    return self.lines;
}

#endif /* SPY_POSIX_H */
