#include "spy/list.h"
#include <string.h>

// same #defines needed here too
#define spy_list_str spy__list$list__builtins$str$_ListImpl
#define spy_list_str_new spy__list$list__builtins$str$_ListImpl$__new__
#define spy_list_str_push spy__list$list__builtins$str$_ListImpl$_push

spy_list_str
spy_wrap_argv(int argc, const char *argv[]) {
    spy_list_str lst = spy_list_str_new();
    for (int i = 0; i < argc; i++) {
        size_t size_str = strlen(argv[i]);
        spy_Str *allo = spy_str_alloc(size_str);
        char *buf = (char *)allo->utf8;
        memcpy(buf, argv[i], size_str);
        lst = spy_list_str_push(lst, allo);
    }
    return lst;
}