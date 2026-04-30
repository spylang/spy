#ifndef SPY_JSFFI_CALL_METHOD_H
#define SPY_JSFFI_CALL_METHOD_H

/* jsffi_call_method.h
 *
 * WASM_EXPORT declarations and spy_jsffi$ inline wrappers for all
 * call_method variants. Included by jsffi.h.
 *
 * See jsffi_call_method.c for details.
 */

/* ------------------------------------------------------------------ */
/* WASM_EXPORT declarations                                           */
/* ------------------------------------------------------------------ */

/* Returning */
JsRef WASM_EXPORT(jsffi_call_method_0)(JsRef c_target, const char *c_name);
JsRef WASM_EXPORT(jsffi_call_method_1)(JsRef c_target, const char *c_name,
                                        JsRef c_arg0);
JsRef WASM_EXPORT(jsffi_call_method_2)(JsRef c_target, const char *c_name,
                                        JsRef c_arg0, JsRef c_arg1);
JsRef WASM_EXPORT(jsffi_call_method_3)(JsRef c_target, const char *c_name,
                                        JsRef c_arg0, JsRef c_arg1, JsRef c_arg2);
JsRef WASM_EXPORT(jsffi_call_method_4)(JsRef c_target, const char *c_name,
                                        JsRef c_arg0, JsRef c_arg1,
                                        JsRef c_arg2, JsRef c_arg3);
JsRef WASM_EXPORT(jsffi_call_method_5)(JsRef c_target, const char *c_name,
                                        JsRef c_arg0, JsRef c_arg1, JsRef c_arg2,
                                        JsRef c_arg3, JsRef c_arg4);
JsRef WASM_EXPORT(jsffi_call_method_6)(JsRef c_target, const char *c_name,
                                        JsRef c_arg0, JsRef c_arg1, JsRef c_arg2,
                                        JsRef c_arg3, JsRef c_arg4, JsRef c_arg5);

/* ------------------------------------------------------------------ */
/* spy_jsffi$ inline wrappers                                           */
/* ------------------------------------------------------------------ */

/* Returning */
static inline JsRef
spy_jsffi$js_call_method_0(JsRef target, spy_Str *name) {
    return jsffi_call_method_0(target, name->utf8);
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
spy_jsffi$js_call_method_3(JsRef target, spy_Str *name,
                            JsRef arg0, JsRef arg1, JsRef arg2) {
    return jsffi_call_method_3(target, name->utf8, arg0, arg1, arg2);
}

static inline JsRef
spy_jsffi$js_call_method_4(JsRef target, spy_Str *name,
                            JsRef arg0, JsRef arg1, JsRef arg2, JsRef arg3) {
    return jsffi_call_method_4(target, name->utf8, arg0, arg1, arg2, arg3);
}

static inline JsRef
spy_jsffi$js_call_method_5(JsRef target, spy_Str *name,
                            JsRef arg0, JsRef arg1, JsRef arg2,
                            JsRef arg3, JsRef arg4) {
    return jsffi_call_method_5(target, name->utf8, arg0, arg1, arg2, arg3, arg4);
}

static inline JsRef
spy_jsffi$js_call_method_6(JsRef target, spy_Str *name,
                            JsRef arg0, JsRef arg1, JsRef arg2,
                            JsRef arg3, JsRef arg4, JsRef arg5) {
    return jsffi_call_method_6(target, name->utf8, arg0, arg1, arg2, arg3, arg4, arg5);
}

#endif /* SPY_JSFFI_CALL_METHOD_H */
