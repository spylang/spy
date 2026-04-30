#ifndef SPY_JSFFI_H
#define SPY_JSFFI_H

#include "emscripten.h"
#include "spy.h"
#include <stddef.h>

typedef struct {
    int id;
} JsRef;


// Def JsVal, used for arguments

typedef enum {
    JSVAL_JSREF = 0,
    JSVAL_F64   = 1,
    JSVAL_I32   = 2,
    JSVAL_STR   = 3,   // const char* into WASM memory, valid for call duration
    JSVAL_BOOL  = 4,
} JsValTag;

typedef struct {
    JsValTag tag;
    union {
        int         jsref_id;
        double      f64;
        int32_t     i32;
        const char *str;
        int         bool_;
    };
} JsVal;

// Constructors
static inline JsVal spy_jsffi$jsval_from_jsref(JsRef r)  { return (JsVal){JSVAL_JSREF, .jsref_id = r.id}; }
static inline JsVal spy_jsffi$jsval_from_f64(double x)   { return (JsVal){JSVAL_F64,   .f64 = x};         }
static inline JsVal spy_jsffi$jsval_from_i32(int32_t x)  { return (JsVal){JSVAL_I32,   .i32 = x};         }
static inline JsVal spy_jsffi$jsval_from_str(spy_Str *s) { return (JsVal){JSVAL_STR,   .str = s->utf8};   }
static inline JsVal spy_jsffi$jsval_from_bool(int x)     { return (JsVal){JSVAL_BOOL,  .bool_ = x};       }

// Extract numeric payload as f64 for passing as two C args to EM_JS
static inline double jsval_payload(JsVal v) {
    switch (v.tag) {
        case JSVAL_F64:   return v.f64;
        case JSVAL_I32:   return (double)v.i32;
        case JSVAL_STR:   return (double)(uintptr_t)v.str;
        case JSVAL_BOOL:  return (double)v.bool_;
        case JSVAL_JSREF: return (double)v.jsref_id;
        default:          return 0.0;
    }
}


// jsffi C interface
JsRef WASM_EXPORT(jsffi_debug)(const char *ptr);
int32_t WASM_EXPORT(jsffi_debug_n_jsrefs)(void);
void WASM_EXPORT(jsffi_init)(void);
JsRef WASM_EXPORT(jsffi_string)(const char *ptr);
JsRef WASM_EXPORT(jsffi_i32)(int32_t x);
JsRef WASM_EXPORT(jsffi_f64)(double x);
JsRef WASM_EXPORT(jsffi_wrap_func)(em_callback_func cfunc);
JsRef WASM_EXPORT(jsffi_wrap_func_f64)(em_callback_func cfunc);
typedef void (*jsffi_frame_func)(double);

#include "jsffi_call_method.h"

void WASM_EXPORT(jsffi_drop_ref)(JsRef c_target);

JsRef WASM_EXPORT(jsffi_getattr)(JsRef c_target, const char *c_name);
void WASM_EXPORT(jsffi_setattr)(JsRef c_target, const char *c_name, int32_t tag0, double val0);

JsRef WASM_EXPORT(jsffi_u8array_from_ptr)(void *ptr, int32_t length);
JsRef WASM_EXPORT(jsffi_new_ImageData)(JsRef c_array, int32_t width, int32_t height);
int32_t WASM_EXPORT(jsffi_to_i32)(JsRef c_ref);
double WASM_EXPORT(jsffi_to_f64)(JsRef c_ref);

// SPy JSFFI module
static inline void
spy_jsffi$debug(spy_Str *s) {
    jsffi_debug(s->utf8);
}

static inline int32_t
spy_jsffi$_debug_n_jsrefs(void) {
    return jsffi_debug_n_jsrefs();
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
spy_jsffi$get_Document(void) {
    return (JsRef){2};
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

static inline void
spy_jsffi$drop_ref(JsRef target) {
    jsffi_drop_ref(target);
}

static inline JsRef
spy_jsffi$JsRef$__getattribute__(JsRef target, spy_Str *name) {
    return jsffi_getattr(target, name->utf8);
}

static inline void
spy_jsffi$JsRef$__setattr__(JsRef target, spy_Str *name, JsVal val) {
    jsffi_setattr(target, name->utf8, val.tag, jsval_payload(val));
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
