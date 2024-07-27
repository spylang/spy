#ifndef SPY_JSFFI_H
#define SPY_JSFFI_H

#include <stddef.h>
#include "emscripten.h"
#include "spy.h"


typedef struct {
    int id;
} JsRef;

// jsffi C interface
JsRef WASM_EXPORT(jsffi_debug)(const char *ptr);
void WASM_EXPORT(jsffi_init)(void);
JsRef WASM_EXPORT(jsffi_string)(const char *ptr);
JsRef WASM_EXPORT(jsffi_i32)(int32_t x);
JsRef WASM_EXPORT(jsffi_wrap_func)(em_callback_func cfunc);
JsRef WASM_EXPORT(jsffi_call_method_1)(JsRef c_target, const char *c_name, JsRef c_arg0);
JsRef WASM_EXPORT(jsffi_getattr)(JsRef c_target, const char *c_name);
void WASM_EXPORT(jsffi_setattr)(JsRef c_target, const char *c_name, JsRef c_val);


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

static inline JsRef spy_jsffi$js_i32(int32_t x) {
    return jsffi_i32(x);
}

static inline JsRef spy_jsffi$js_wrap_func(em_callback_func fn) {
    return jsffi_wrap_func(fn);
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


/* This is a workaround for an emscripten bug/limitation which triggers in the
   following case:

   1. you have jsffi.c which contains only EM_JS functions

   2. you put jsffi.o into libspy.a

   3. you have main.c and you try to link main.o and libspy.a

   In this case, emscripten is unable to understand that it must include
   jsffi.o the final executable, and you get undefined symbols.

   The workaround is to make sure that we have a reference to at least ONE
   symbol which is non-EM_JS in main.c, and this is done by the following
   lines:
*/

void jsffi_force_include(void);
void* _jsffi_force_include __attribute__((weak)) = jsffi_force_include;

#endif /* SPY_JSFFI_H */
