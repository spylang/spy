#ifndef SPY___SPY___H
#define SPY___SPY___H

#include "spy/str.h"
#include <stdbool.h>
#include <stdio.h>

static inline bool
spy___spy__$is_compiled(void) {
    return true;
}

static inline void
spy___spy__$_stdout_write(spy_StrObject *s) {
    for (size_t i = 0; i < s->length; i++)
        putchar(spy_StrObject_UTF8(s)[i]);
}

static inline void
spy___spy__$_stdout_flush(void) {
    fflush(stdout);
}

static inline spy_StrObject *
spy___spy__$_stdin_readline(void) {
    char *line = NULL;
    size_t bufsize = 0;
    ssize_t n = getline(&line, &bufsize, stdin);
    if (n < 0) {
        free(line);
        if (ferror(stdin)) {
            spy_panic("OSError", "stdin read error", __FILE__, __LINE__);
        }
        // EOF: mimic CPython's input(), which raises EOFError
        spy_panic("EOFError", "EOF when reading a line", __FILE__, __LINE__);
        return NULL;
    }
    // strip the trailing newline (and \r, to handle CRLF line endings)
    if (n > 0 && line[n - 1] == '\n')
        n--;
    if (n > 0 && line[n - 1] == '\r')
        n--;
    spy_StrObject *res = spy_str_alloc(n);
    memcpy((char *)spy_StrObject_UTF8(res), line, n);
    free(line);
    return res;
}

#endif /* SPY___SPY___H */
