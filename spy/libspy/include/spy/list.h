#ifndef SPY_LIST_H
#define SPY_LIST_H

#include "spy.h"

// Give human names to list[str] FQNs
#define spy_list_str spy__list$list__builtins$str$_ListImpl
#define spy_list_str_new spy__list$list__builtins$str$_ListImpl$__new__
#define spy_list_str_push spy__list$list__builtins$str$_ListImpl$_push

spy_list_str spy_list_str_new(void);
spy_list_str spy_list_str_push(spy_list_str self, spy_Str *item);

// Convert C argc/argv into a SPy list[str]
spy_list_str spy_wrap_argv(int argc, const char *argv[]);

#endif /* SPY_LIST_H */