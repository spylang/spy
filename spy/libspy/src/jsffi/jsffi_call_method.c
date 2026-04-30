/* jsffi_call_method.c
 *
 * Variants of jsffi_call_method_N for N=0..6.
 * This file is #included by jsffi.c (unity build) so that all EM_JS
 * functions share the same translation unit and can access the `jsffi`
 * object initialised by jsffi_init().
 *
 * Arguments are passed as (int32_t tagN, double valN) pairs — JsVal split
 * into two C scalars — so that primitive values bypass jsffi.objects entirely.
 */

EM_JS(JsRef, jsffi_call_method_0, (JsRef c_target, const char *c_name), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let res = target[name].call(target);
    return jsffi.to_jsref(res);
});

EM_JS(JsRef, jsffi_call_method_1, (JsRef c_target, const char *c_name,
                                    int32_t tag0, double val0), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let res = target[name].call(target,
        jsffi.from_jsval(tag0, val0));
    return jsffi.to_jsref(res);
});

EM_JS(JsRef, jsffi_call_method_2, (JsRef c_target, const char *c_name,
                                    int32_t tag0, double val0, int32_t tag1, double val1), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let res = target[name].call(target,
        jsffi.from_jsval(tag0, val0),
        jsffi.from_jsval(tag1, val1));
    return jsffi.to_jsref(res);
});

EM_JS(JsRef, jsffi_call_method_3, (JsRef c_target, const char *c_name,
                                    int32_t tag0, double val0, int32_t tag1, double val1,
                                    int32_t tag2, double val2), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let res = target[name].call(target,
        jsffi.from_jsval(tag0, val0),
        jsffi.from_jsval(tag1, val1),
        jsffi.from_jsval(tag2, val2));
    return jsffi.to_jsref(res);
});

EM_JS(JsRef, jsffi_call_method_4, (JsRef c_target, const char *c_name,
                                    int32_t tag0, double val0, int32_t tag1, double val1,
                                    int32_t tag2, double val2, int32_t tag3, double val3), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let res = target[name].call(target,
        jsffi.from_jsval(tag0, val0),
        jsffi.from_jsval(tag1, val1),
        jsffi.from_jsval(tag2, val2),
        jsffi.from_jsval(tag3, val3));
    return jsffi.to_jsref(res);
});

EM_JS(JsRef, jsffi_call_method_5, (JsRef c_target, const char *c_name,
                                    int32_t tag0, double val0, int32_t tag1, double val1,
                                    int32_t tag2, double val2, int32_t tag3, double val3,
                                    int32_t tag4, double val4), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let res = target[name].call(target,
        jsffi.from_jsval(tag0, val0),
        jsffi.from_jsval(tag1, val1),
        jsffi.from_jsval(tag2, val2),
        jsffi.from_jsval(tag3, val3),
        jsffi.from_jsval(tag4, val4));
    return jsffi.to_jsref(res);
});

EM_JS(JsRef, jsffi_call_method_6, (JsRef c_target, const char *c_name,
                                    int32_t tag0, double val0, int32_t tag1, double val1,
                                    int32_t tag2, double val2, int32_t tag3, double val3,
                                    int32_t tag4, double val4, int32_t tag5, double val5), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let res = target[name].call(target,
        jsffi.from_jsval(tag0, val0),
        jsffi.from_jsval(tag1, val1),
        jsffi.from_jsval(tag2, val2),
        jsffi.from_jsval(tag3, val3),
        jsffi.from_jsval(tag4, val4),
        jsffi.from_jsval(tag5, val5));
    return jsffi.to_jsref(res);
});

