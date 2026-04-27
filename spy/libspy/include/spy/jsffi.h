#ifndef SPY_JSFFI_H
#define SPY_JSFFI_H

#include "emscripten.h"
#include "spy.h"
#include <stddef.h>

typedef struct {
    int id;
} JsRef;

// jsffi C interface
JsRef WASM_EXPORT(jsffi_debug)(const char *ptr);
void WASM_EXPORT(jsffi_init)(void);
JsRef WASM_EXPORT(jsffi_string)(const char *ptr);
JsRef WASM_EXPORT(jsffi_i32)(int32_t x);
JsRef WASM_EXPORT(jsffi_f64)(double x);
JsRef WASM_EXPORT(jsffi_wrap_func)(em_callback_func cfunc);
JsRef WASM_EXPORT(jsffi_wrap_func_f64)(em_callback_func cfunc);
typedef void (*jsffi_frame_func)(double);
JsRef WASM_EXPORT(jsffi_call_method_1)(
    JsRef c_target,
    const char *c_name,
    JsRef c_arg0
);
JsRef WASM_EXPORT(jsffi_call_method_2)(
    JsRef c_target,
    const char *c_name,
    JsRef c_arg0,
    JsRef c_arg1
);
JsRef WASM_EXPORT(jsffi_call_method_3)(
    JsRef c_target,
    const char *c_name,
    JsRef c_arg0,
    JsRef c_arg1,
    JsRef c_arg2
);
JsRef WASM_EXPORT(jsffi_getattr)(JsRef c_target, const char *c_name);
void WASM_EXPORT(jsffi_setattr)(JsRef c_target, const char *c_name, JsRef c_val);

JsRef WASM_EXPORT(jsffi_u8array_from_ptr)(void *ptr, int32_t length);
JsRef WASM_EXPORT(jsffi_new_ImageData)(JsRef c_array, int32_t width, int32_t height);
int32_t WASM_EXPORT(jsffi_to_i32)(JsRef c_ref);
double WASM_EXPORT(jsffi_to_f64)(JsRef c_ref);

// SPy JSFFI module
static inline void
spy_jsffi$debug(spy_Str *s) {
    jsffi_debug(s->utf8);
}

static inline void
spy_jsffi$init(void) {
    jsffi_init();
}

static inline JsRef
spy_jsffi$get_GlobalThis(void) {
    return (JsRef){0};
}

static inline JsRef
spy_jsffi$get_Console(void) {
    return (JsRef){1};
}

static inline JsRef
spy_jsffi$js_string(spy_Str *s) {
    return jsffi_string(s->utf8);
}

static inline JsRef
spy_jsffi$js_i32(int32_t x) {
    return jsffi_i32(x);
}

static inline JsRef
spy_jsffi$js_f64(double x) {
    return jsffi_f64(x);
}

static inline JsRef
spy_jsffi$js_wrap_func(em_callback_func fn) {
    return jsffi_wrap_func(fn);
}

static inline JsRef
spy_jsffi$js_wrap_func_f64(jsffi_frame_func fn) {
    return jsffi_wrap_func_f64((em_callback_func)fn);
}

static inline JsRef
spy_jsffi$js_call_method_1(JsRef target, spy_Str *name, JsRef arg0) {
    return jsffi_call_method_1(target, name->utf8, arg0);
}

static inline JsRef
spy_jsffi$js_call_method_2(JsRef target, spy_Str *name, JsRef arg0, JsRef arg1) {
    return jsffi_call_method_2(target, name->utf8, arg0, arg1);
}

static inline JsRef
spy_jsffi$js_call_method_3(JsRef target, spy_Str *name, JsRef arg0, JsRef arg1, JsRef arg2) {
    return jsffi_call_method_3(target, name->utf8, arg0, arg1, arg2);
}

static inline JsRef
spy_jsffi$JsRef$__getattribute__(JsRef target, spy_Str *name) {
    return jsffi_getattr(target, name->utf8);
}

static inline void
spy_jsffi$JsRef$__setattr__(JsRef target, spy_Str *name, JsRef val) {
    jsffi_setattr(target, name->utf8, val);
}

// Use a macro so it works with any ptr type (gc_ptr, raw_ptr)
#define spy_jsffi$js_u8array_from_ptr(ptr, length) \
    jsffi_u8array_from_ptr((void *)(ptr).p, length)

static inline JsRef
spy_jsffi$js_new_ImageData(JsRef array, int32_t width, int32_t height) {
    return jsffi_new_ImageData(array, width, height);
}

static inline int32_t
spy_jsffi$js_to_i32(JsRef ref) {
    return jsffi_to_i32(ref);
}

static inline double
spy_jsffi$js_to_f64(JsRef ref) {
    return jsffi_to_f64(ref);
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
void *_jsffi_force_include __attribute__((weak)) = jsffi_force_include;

#endif /* SPY_JSFFI_H */
