/* jsffi_call_method.c
 *
 * Variants of jsffi_call_method_N for N=0..6.
 * This file is #included by jsffi.c (unity build) so that all EM_JS
 * functions share the same translation unit and can access the `jsffi`
 * object initialised by jsffi_init().
 *
 * Three families:
 *   jsffi_call_method_N          — returns JsRef (result stored in jsffi.objects)
 *   jsffi_call_method_N_void     — discards return value, no JsRef created
 *   jsffi_call_method_N_f64_void — all args are raw C doubles (no JsRef wrapping),
 *                                   discards return value; zero jsffi.objects growth
 */

/* ------------------------------------------------------------------ */
/* Returning variants                                                 */
/* ------------------------------------------------------------------ */

EM_JS(JsRef, jsffi_call_method_0, (JsRef c_target, const char *c_name), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let res = target[name].call(target);
    return jsffi.to_jsref(res);
});

EM_JS(JsRef, jsffi_call_method_1, (JsRef c_target, const char *c_name,
                                    JsRef c_arg0), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let res = target[name].call(target,
        jsffi.from_jsref(c_arg0));
    return jsffi.to_jsref(res);
});

EM_JS(JsRef, jsffi_call_method_2, (JsRef c_target, const char *c_name,
                                    JsRef c_arg0, JsRef c_arg1), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let res = target[name].call(target,
        jsffi.from_jsref(c_arg0),
        jsffi.from_jsref(c_arg1));
    return jsffi.to_jsref(res);
});

EM_JS(JsRef, jsffi_call_method_3, (JsRef c_target, const char *c_name,
                                    JsRef c_arg0, JsRef c_arg1, JsRef c_arg2), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let res = target[name].call(target,
        jsffi.from_jsref(c_arg0),
        jsffi.from_jsref(c_arg1),
        jsffi.from_jsref(c_arg2));
    return jsffi.to_jsref(res);
});

EM_JS(JsRef, jsffi_call_method_4, (JsRef c_target, const char *c_name,
                                    JsRef c_arg0, JsRef c_arg1,
                                    JsRef c_arg2, JsRef c_arg3), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let res = target[name].call(target,
        jsffi.from_jsref(c_arg0),
        jsffi.from_jsref(c_arg1),
        jsffi.from_jsref(c_arg2),
        jsffi.from_jsref(c_arg3));
    return jsffi.to_jsref(res);
});

EM_JS(JsRef, jsffi_call_method_5, (JsRef c_target, const char *c_name,
                                    JsRef c_arg0, JsRef c_arg1, JsRef c_arg2,
                                    JsRef c_arg3, JsRef c_arg4), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let res = target[name].call(target,
        jsffi.from_jsref(c_arg0),
        jsffi.from_jsref(c_arg1),
        jsffi.from_jsref(c_arg2),
        jsffi.from_jsref(c_arg3),
        jsffi.from_jsref(c_arg4));
    return jsffi.to_jsref(res);
});

EM_JS(JsRef, jsffi_call_method_6, (JsRef c_target, const char *c_name,
                                    JsRef c_arg0, JsRef c_arg1, JsRef c_arg2,
                                    JsRef c_arg3, JsRef c_arg4, JsRef c_arg5), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let res = target[name].call(target,
        jsffi.from_jsref(c_arg0),
        jsffi.from_jsref(c_arg1),
        jsffi.from_jsref(c_arg2),
        jsffi.from_jsref(c_arg3),
        jsffi.from_jsref(c_arg4),
        jsffi.from_jsref(c_arg5));
    return jsffi.to_jsref(res);
});

/* ------------------------------------------------------------------ */
/* Void variants (discard return value)                               */
/* ------------------------------------------------------------------ */

EM_JS(void, jsffi_call_method_0_void, (JsRef c_target, const char *c_name), {
    let target = jsffi.from_jsref(c_target);
    target[UTF8ToString(c_name)].call(target);
});

EM_JS(void, jsffi_call_method_1_void, (JsRef c_target, const char *c_name,
                                        JsRef c_arg0), {
    let target = jsffi.from_jsref(c_target);
    target[UTF8ToString(c_name)].call(target,
        jsffi.from_jsref(c_arg0));
});

EM_JS(void, jsffi_call_method_2_void, (JsRef c_target, const char *c_name,
                                        JsRef c_arg0, JsRef c_arg1), {
    let target = jsffi.from_jsref(c_target);
    target[UTF8ToString(c_name)].call(target,
        jsffi.from_jsref(c_arg0),
        jsffi.from_jsref(c_arg1));
});

EM_JS(void, jsffi_call_method_3_void, (JsRef c_target, const char *c_name,
                                        JsRef c_arg0, JsRef c_arg1, JsRef c_arg2), {
    let target = jsffi.from_jsref(c_target);
    target[UTF8ToString(c_name)].call(target,
        jsffi.from_jsref(c_arg0),
        jsffi.from_jsref(c_arg1),
        jsffi.from_jsref(c_arg2));
});

EM_JS(void, jsffi_call_method_4_void, (JsRef c_target, const char *c_name,
                                        JsRef c_arg0, JsRef c_arg1,
                                        JsRef c_arg2, JsRef c_arg3), {
    let target = jsffi.from_jsref(c_target);
    target[UTF8ToString(c_name)].call(target,
        jsffi.from_jsref(c_arg0),
        jsffi.from_jsref(c_arg1),
        jsffi.from_jsref(c_arg2),
        jsffi.from_jsref(c_arg3));
});

EM_JS(void, jsffi_call_method_5_void, (JsRef c_target, const char *c_name,
                                        JsRef c_arg0, JsRef c_arg1, JsRef c_arg2,
                                        JsRef c_arg3, JsRef c_arg4), {
    let target = jsffi.from_jsref(c_target);
    target[UTF8ToString(c_name)].call(target,
        jsffi.from_jsref(c_arg0),
        jsffi.from_jsref(c_arg1),
        jsffi.from_jsref(c_arg2),
        jsffi.from_jsref(c_arg3),
        jsffi.from_jsref(c_arg4));
});

EM_JS(void, jsffi_call_method_6_void, (JsRef c_target, const char *c_name,
                                        JsRef c_arg0, JsRef c_arg1, JsRef c_arg2,
                                        JsRef c_arg3, JsRef c_arg4, JsRef c_arg5), {
    let target = jsffi.from_jsref(c_target);
    target[UTF8ToString(c_name)].call(target,
        jsffi.from_jsref(c_arg0),
        jsffi.from_jsref(c_arg1),
        jsffi.from_jsref(c_arg2),
        jsffi.from_jsref(c_arg3),
        jsffi.from_jsref(c_arg4),
        jsffi.from_jsref(c_arg5));
});

/* ------------------------------------------------------------------ */
/* f64-void variants (raw double args, discard return value)          */
/* Used for hot-path canvas calls where all args are f64:             */
/*   moveTo(x,y)  lineTo(x,y)  fillRect(x,y,w,h)  arc(x,y,r,s,e)      */
/* Zero jsffi.objects growth — args bypass the JsRef store entirely.  */
/* ------------------------------------------------------------------ */

EM_JS(void, jsffi_call_method_2_f64_void, (JsRef c_target, const char *c_name,
                                            double a0, double a1), {
    let target = jsffi.from_jsref(c_target);
    target[UTF8ToString(c_name)].call(target, a0, a1);
});

EM_JS(void, jsffi_call_method_3_f64_void, (JsRef c_target, const char *c_name,
                                            double a0, double a1, double a2), {
    let target = jsffi.from_jsref(c_target);
    target[UTF8ToString(c_name)].call(target, a0, a1, a2);
});

EM_JS(void, jsffi_call_method_4_f64_void, (JsRef c_target, const char *c_name,
                                            double a0, double a1,
                                            double a2, double a3), {
    let target = jsffi.from_jsref(c_target);
    target[UTF8ToString(c_name)].call(target, a0, a1, a2, a3);
});

EM_JS(void, jsffi_call_method_5_f64_void, (JsRef c_target, const char *c_name,
                                            double a0, double a1, double a2,
                                            double a3, double a4), {
    let target = jsffi.from_jsref(c_target);
    target[UTF8ToString(c_name)].call(target, a0, a1, a2, a3, a4);
});
