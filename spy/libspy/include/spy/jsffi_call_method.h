#ifndef SPY_JSFFI_CALL_METHOD_H
#define SPY_JSFFI_CALL_METHOD_H

/* jsffi_call_method.h
 *
 * WASM_EXPORT declarations and spy_jsffi$ inline wrappers for all
 * call_method variants. Included by jsffi.h.
 *
 * Each JsVal argument is split into (int32_t tagN, double valN).
 * The spy_jsffi$ wrappers accept JsVal structs and expand them.
 * See jsffi_call_method.c for details.
 */

/* ------------------------------------------------------------------ */
/* WASM_EXPORT declarations                                           */
/* ------------------------------------------------------------------ */

JsRef WASM_EXPORT(jsffi_call_method_0)(JsRef c_target, const char *c_name);
JsRef WASM_EXPORT(jsffi_call_method_1)(JsRef c_target, const char *c_name,
                                        int32_t tag0, double val0);
JsRef WASM_EXPORT(jsffi_call_method_2)(JsRef c_target, const char *c_name,
                                        int32_t tag0, double val0, int32_t tag1, double val1);
JsRef WASM_EXPORT(jsffi_call_method_3)(JsRef c_target, const char *c_name,
                                        int32_t tag0, double val0, int32_t tag1, double val1,
                                        int32_t tag2, double val2);
JsRef WASM_EXPORT(jsffi_call_method_4)(JsRef c_target, const char *c_name,
                                        int32_t tag0, double val0, int32_t tag1, double val1,
                                        int32_t tag2, double val2, int32_t tag3, double val3);
JsRef WASM_EXPORT(jsffi_call_method_5)(JsRef c_target, const char *c_name,
                                        int32_t tag0, double val0, int32_t tag1, double val1,
                                        int32_t tag2, double val2, int32_t tag3, double val3,
                                        int32_t tag4, double val4);
JsRef WASM_EXPORT(jsffi_call_method_6)(JsRef c_target, const char *c_name,
                                        int32_t tag0, double val0, int32_t tag1, double val1,
                                        int32_t tag2, double val2, int32_t tag3, double val3,
                                        int32_t tag4, double val4, int32_t tag5, double val5);

/* ------------------------------------------------------------------ */
/* spy_jsffi$ inline wrappers                                         */
/* ------------------------------------------------------------------ */

static inline JsRef
spy_jsffi$js_call_method_0(JsRef target, spy_Str *name) {
    return jsffi_call_method_0(target, name->utf8);
}
static inline JsRef
spy_jsffi$js_call_method_1(JsRef target, spy_Str *name, JsVal arg0) {
    return jsffi_call_method_1(target, name->utf8,
                               arg0.tag, jsval_payload(arg0));
}
static inline JsRef
spy_jsffi$js_call_method_2(JsRef target, spy_Str *name, JsVal arg0, JsVal arg1) {
    return jsffi_call_method_2(target, name->utf8,
                               arg0.tag, jsval_payload(arg0),
                               arg1.tag, jsval_payload(arg1));
}
static inline JsRef
spy_jsffi$js_call_method_3(JsRef target, spy_Str *name, JsVal arg0, JsVal arg1, JsVal arg2) {
    return jsffi_call_method_3(target, name->utf8,
                               arg0.tag, jsval_payload(arg0),
                               arg1.tag, jsval_payload(arg1),
                               arg2.tag, jsval_payload(arg2));
}
static inline JsRef
spy_jsffi$js_call_method_4(JsRef target, spy_Str *name,
                            JsVal arg0, JsVal arg1, JsVal arg2, JsVal arg3) {
    return jsffi_call_method_4(target, name->utf8,
                               arg0.tag, jsval_payload(arg0),
                               arg1.tag, jsval_payload(arg1),
                               arg2.tag, jsval_payload(arg2),
                               arg3.tag, jsval_payload(arg3));
}
static inline JsRef
spy_jsffi$js_call_method_5(JsRef target, spy_Str *name,
                            JsVal arg0, JsVal arg1, JsVal arg2, JsVal arg3, JsVal arg4) {
    return jsffi_call_method_5(target, name->utf8,
                               arg0.tag, jsval_payload(arg0),
                               arg1.tag, jsval_payload(arg1),
                               arg2.tag, jsval_payload(arg2),
                               arg3.tag, jsval_payload(arg3),
                               arg4.tag, jsval_payload(arg4));
}
static inline JsRef
spy_jsffi$js_call_method_6(JsRef target, spy_Str *name,
                            JsVal arg0, JsVal arg1, JsVal arg2, JsVal arg3, JsVal arg4, JsVal arg5) {
    return jsffi_call_method_6(target, name->utf8,
                               arg0.tag, jsval_payload(arg0),
                               arg1.tag, jsval_payload(arg1),
                               arg2.tag, jsval_payload(arg2),
                               arg3.tag, jsval_payload(arg3),
                               arg4.tag, jsval_payload(arg4),
                               arg5.tag, jsval_payload(arg5));
}

#endif /* SPY_JSFFI_CALL_METHOD_H */
