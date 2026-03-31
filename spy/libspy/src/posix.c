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

void
spy_posix$_fclose(FILE *f) {
    fclose(f);
}
