#ifndef SPY_JSFFI_H
#define SPY_JSFFI_H

#include <stddef.h>
#include "spy.h"

typedef struct {
    int id;
} JsRef;

void spy_jsffi$debug(spy_Str *s);
void spy_jsffi$init(void);
JsRef spy_jsffi$get_GlobalThis(void);
JsRef spy_jsffi$get_Console(void);

#endif /* SPY_JSFFI_H */
