#include "spy.h"
#include <stdio.h>

FILE *
spy_posix$_fopen(spy_Str *filename) {
    // spy_Str is not null-terminated, make a temporary copy for fopen
    char *fname = (char *)malloc(filename->length + 1);
    memcpy(fname, filename->utf8, filename->length);
    fname[filename->length] = '\0';

    FILE *f = fopen(fname, "r");
    free(fname);
    if (f == NULL) {
        spy_panic("OSError", "cannot open file", __FILE__, __LINE__);
        return NULL;
    }
    return f;
}

void
spy_posix$_fclose(FILE *f) {
    fclose(f);
}
