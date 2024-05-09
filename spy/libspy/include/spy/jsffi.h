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

JsRef spy_jsffi$js_string(spy_Str *s);
JsRef spy_jsffi$js_call_method_1(JsRef target, spy_Str *name, JsRef arg0);
JsRef spy_jsffi$js_getattr(JsRef target, spy_Str *name);

#endif /* SPY_JSFFI_H */
