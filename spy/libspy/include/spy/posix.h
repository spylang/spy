#ifndef SPY_POSIX_H
#define SPY_POSIX_H

#ifndef SPY_TARGET_WASI
#  include <sys/ioctl.h>
#endif
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>

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

static inline int32_t
spy_posix$open(spy_Str *path, int32_t flags) {
    // path->utf8 is NOT null-terminated, so we need a temporary copy
    char *cpath = (char *)malloc(path->length + 1);
    memcpy(cpath, path->utf8, path->length);
    cpath[path->length] = '\0';
    int fd = open(cpath, flags);
    free(cpath);
    if (fd == -1) {
        spy_panic("ValueError", strerror(errno), __FILE__, __LINE__);
    }
    return (int32_t)fd;
}

static inline spy_Str *
spy_posix$read(int32_t fd, int32_t count) {
    spy_Str *result = spy_str_alloc((size_t)count);
    ssize_t n = read(fd, (void *)result->utf8, (size_t)count);
    if (n == -1) {
        spy_panic("ValueError", strerror(errno), __FILE__, __LINE__);
    }
    // Adjust the length to what was actually read
    result->length = (size_t)n;
    result->hash = -1;
    return result;
}

static inline int32_t
spy_posix$write(int32_t fd, spy_Str *data) {
    ssize_t n = write(fd, data->utf8, data->length);
    if (n == -1) {
        spy_panic("ValueError", strerror(errno), __FILE__, __LINE__);
    }
    return (int32_t)n;
}

static inline void
spy_posix$close(int32_t fd) {
    if (close(fd) == -1) {
        spy_panic("ValueError", strerror(errno), __FILE__, __LINE__);
    }
}

#endif /* SPY_POSIX_H */
