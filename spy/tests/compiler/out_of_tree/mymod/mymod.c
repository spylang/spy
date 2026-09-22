#include "mymod.h"
#include <spy/str.h>
#include <string.h>

static const char NAME[] = "hello from mymod";

spy_StrObject *spy_mymod$get_name(void) {
    size_t n = sizeof(NAME) - 1;
    spy_StrObject *s = spy_str_alloc(n);
    memcpy(spy_StrObject_UTF8(s), NAME, n);
    return s;
}
