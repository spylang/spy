#include "spy.h"
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>

#if !defined(SPY_TARGET_WASI)

void spy_debug_log(const char *s) {
    printf("%s\n", s);
}

void spy_debug_log_i32(const char *s, int32_t n) {
    printf("%s %d\n", s, n);
}

/* Helper function to read a specific line from a file */
static char* read_line_from_file(const char *filename, int line_number) {
    FILE *file;
    char *line = NULL;
    size_t len = 0;
    ssize_t read;
    int current_line = 1;

    if (filename == NULL) {
        return NULL;
    }

    file = fopen(filename, "r");
    if (file == NULL) {
        return NULL;
    }

    while ((read = getline(&line, &len, file)) != -1) {
        if (current_line == line_number) {
            /* Remove trailing newline if present */
            if (read > 0 && line[read-1] == '\n') {
                line[read-1] = '\0';
            }
            fclose(file);
            return line;
        }
        current_line++;
    }

    /* Line not found */
    free(line);
    fclose(file);
    return NULL;
}

void spy_panic(const char *etype, const char *message,
               const char *fname, int32_t lineno) {
    /* write the error message to stderr, formatted line this:
          panic: IndexError: hello
             --> /tmp/prova.spy:2:2
            2 |     raise IndexError("hello")
              |  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    */
    fprintf(stderr, "%s: %s\n", etype, message);
    fprintf(stderr, "   --> %s:%d\n", fname, lineno);

    char *line_content = read_line_from_file(fname, lineno);
    if (line_content != NULL) {
        fprintf(stderr, "%3d | %s\n", lineno, line_content);

        /* Print the indicator line with carets */
        fprintf(stderr, "    | ");
        int i;
        for (i = 0; i < strlen(line_content); i++) {
            fprintf(stderr, "^");
        }
        fprintf(stderr, "\n");

        free(line_content);
    } else {
        /* Couldn't read the line, just show line number */
        fprintf(stderr, "%3d | <unable to read source line>\n", lineno);
        fprintf(stderr, "    | ^\n");
    }

    abort();
}

#endif /* !defined(SPY_TARGET_WASI) */
