#include "spy.h"
#include <stdio.h>

// Parse a spy_Str mode into a C fopen mode string.
// Valid modes contain exactly one of 'r', 'w', 'a', and optionally '+'.
// Returns false if the mode is invalid; otherwise writes the normalized
// mode into `out` (which must have room for at least 3 bytes).
static bool
spy_posix$_parse_mode(spy_Str *mode, char *out) {
    char base = 0;
    bool plus = false;
    for (int32_t i = 0; i < mode->length; i++) {
        char c = mode->utf8[i];
        if (c == 'r' || c == 'w' || c == 'a') {
            if (base != 0)
                return false;
            base = c;
        } else if (c == '+') {
            if (plus)
                return false;
            plus = true;
        } else {
            return false;
        }
    }
    if (base == 0)
        return false;
    out[0] = base;
    if (plus) {
        out[1] = '+';
        out[2] = '\0';
    } else {
        out[1] = '\0';
    }
    return true;
}

FILE *
spy_posix$_fopen(spy_Str *filename, spy_Str *mode) {
    char cmode[3];
    if (!spy_posix$_parse_mode(mode, cmode)) {
        spy_panic("PanicError", "invalid mode for _fopen", __FILE__, __LINE__);
        return NULL;
    }

    // spy_Str is not null-terminated, make a temporary copy for fopen
    char *fname = (char *)malloc(filename->length + 1);
    memcpy(fname, filename->utf8, filename->length);
    fname[filename->length] = '\0';

    FILE *f = fopen(fname, cmode);
    free(fname);
    if (f == NULL) {
        spy_panic("OSError", "cannot open file", __FILE__, __LINE__);
        return NULL;
    }
    return f;
}

spy_Str *
spy_posix$_fread(FILE *f, int32_t size) {
    spy_Str *res = spy_str_alloc(size);
    size_t n = fread((char *)res->utf8, 1, size, f);
    if (n < (size_t)size) {
        // short read: reallocate to actual size
        spy_Str *trimmed = spy_str_alloc(n);
        memcpy((char *)trimmed->utf8, res->utf8, n);
        res = trimmed;
    }
    return res;
}

spy_Str *
spy_posix$__freadall_chunked(FILE *f) {
    size_t capacity = 4096;
    size_t total = 0;
    char *buf = (char *)malloc(capacity);
    while (1) {
        size_t n = fread(buf + total, 1, capacity - total, f);
        total += n;
        if (n == 0)
            break;
        if (total == capacity) {
            capacity *= 2;
            buf = (char *)realloc(buf, capacity);
        }
    }
    if (ferror(f)) {
        free(buf);
        spy_panic("OSError", "freadall: read error", __FILE__, __LINE__);
        return NULL;
    }
    spy_Str *res = spy_str_alloc(total);
    memcpy((char *)res->utf8, buf, total);
    free(buf);
    return res;
}

static bool
spy_posix$_is_seekable(FILE *f) {
    long cur = ftell(f);
    if (cur < 0 || fseek(f, 0, SEEK_END) != 0)
        return false;
    fseek(f, cur, SEEK_SET);
    return true;
}

spy_Str *
spy_posix$_freadall(FILE *f) {
    if (!spy_posix$_is_seekable(f))
        return spy_posix$__freadall_chunked(f);

    long cur = ftell(f);
    fseek(f, 0, SEEK_END);
    long end = ftell(f);
    fseek(f, cur, SEEK_SET);
    size_t size = end - cur;
    spy_Str *res = spy_str_alloc(size);
    size_t n = fread((char *)res->utf8, 1, size, f);
    if (n < size) {
        if (ferror(f)) {
            spy_panic("OSError", "freadall: read error", __FILE__, __LINE__);
            return NULL;
        }
        // EOF before expected: e.g. file was truncated concurrently
        spy_Str *trimmed = spy_str_alloc(n);
        memcpy((char *)trimmed->utf8, res->utf8, n);
        res = trimmed;
    }
    return res;
}

spy_Str *
spy_posix$_freadline(FILE *f) {
    char *line = NULL;
    size_t bufsize = 0;
    ssize_t n = getline(&line, &bufsize, f);
    if (n < 0) {
        free(line);
        if (ferror(f)) {
            spy_panic("OSError", "freadline: read error", __FILE__, __LINE__);
            return NULL;
        }
        // EOF: return empty string
        return spy_str_alloc(0);
    }
    spy_Str *res = spy_str_alloc(n);
    memcpy((char *)res->utf8, line, n);
    free(line);
    return res;
}

int32_t
spy_posix$_ftell(FILE *f) {
    long pos = ftell(f);
    if (pos < 0) {
        spy_panic("OSError", "ftell failed", __FILE__, __LINE__);
        return -1;
    }
    return (int32_t)pos;
}

void
spy_posix$_fseek(FILE *f, int32_t offset, int32_t whence) {
    if (fseek(f, offset, whence) != 0) {
        spy_panic("OSError", "fseek failed", __FILE__, __LINE__);
    }
}

void
spy_posix$_fwrite(FILE *f, spy_Str *data) {
    size_t n = fwrite(data->utf8, 1, data->length, f);
    if (n < data->length) {
        spy_panic("OSError", "fwrite: write error", __FILE__, __LINE__);
    }
}

void
spy_posix$_fflush(FILE *f) {
    fflush(f);
}

int32_t
spy_posix$_fileno(FILE *f) {
    return fileno(f);
}

bool
spy_posix$_isatty(int32_t fd) {
    return isatty(fd);
}

void
spy_posix$_fclose(FILE *f) {
    fclose(f);
}
