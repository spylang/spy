/* jsffi_call_method.c
 *
 * Variants of jsffi_call_method_N for N=0..6.
 * This file is #included by jsffi.c (unity build) so that all EM_JS
 * functions share the same translation unit and can access the `jsffi`
 * object initialised by jsffi_init().
 */

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
