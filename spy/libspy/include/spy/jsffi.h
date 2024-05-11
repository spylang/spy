#ifndef SPY_JSFFI_H
#define SPY_JSFFI_H

#include <stddef.h>
#include "emscripten.h"
#include "spy.h"


typedef struct {
    int id;
} JsRef;

// jsffi C interface
JsRef jsffi_debug(const char *ptr);
void jsffi_init(void);
JsRef jsffi_string(const char *ptr);
JsRef jsffi_wrap_func(em_callback_func cfunc);
JsRef jsffi_call_method_1(JsRef c_target, const char *c_name, JsRef c_arg0);
JsRef jsffi_getattr(JsRef c_target, const char *c_name);
void jsffi_setattr(JsRef c_target, const char *c_name, JsRef c_val);


// SPy JSFFI module
static inline void spy_jsffi$debug(spy_Str *s) {
    jsffi_debug(s->utf8);
}

static inline void spy_jsffi$init(void) {
    jsffi_init();
}

static inline JsRef spy_jsffi$get_GlobalThis(void) {
    return (JsRef){0};
}

static inline JsRef spy_jsffi$get_Console(void) {
    return (JsRef){1};
}

static inline JsRef spy_jsffi$js_string(spy_Str *s) {
    return jsffi_string(s->utf8);
}

static inline JsRef spy_jsffi$js_call_method_1(
                                 JsRef target, spy_Str *name, JsRef arg0) {
    return jsffi_call_method_1(target, name->utf8, arg0);
}

static inline JsRef spy_jsffi$js_getattr(JsRef target, spy_Str *name) {
    return jsffi_getattr(target, name->utf8);
}

static inline void spy_jsffi$js_setattr(
                                 JsRef target, spy_Str *name, JsRef val) {
    jsffi_setattr(target, name->utf8, val);
}

#endif /* SPY_JSFFI_H */
