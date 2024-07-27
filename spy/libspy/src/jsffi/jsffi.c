#include <emscripten.h>
#include "spy.h"

EM_JS_DEPS(jsffi, "$UTF8ToString,$wasmTable");

// see the corresponding comment in jsffi.h
void jsffi_force_include(void) {
}

EM_JS(JsRef, jsffi_debug, (const char *ptr), {
    let s = UTF8ToString(ptr);
    console.log(s);
});

EM_JS(void, jsffi_init, (void), {
    let jsffi = {
        objects: {}
    };
    globalThis.jsffi = jsffi;
    jsffi.objects[0] = globalThis;
    jsffi.objects[1] = console;

    jsffi.from_jsref = function(idval) {
        if (idval in jsffi.objects) {
            return jsffi.objects[idval];
        }
        //console.log(jsffi.objects);
        console.error(`jsffi internal error: Undefined id ${ idval }`);
        throw new Error(`Undefined id ${ idval }`);
    };

    jsffi.to_jsref = function(jsval) {
        let n = Object.keys(jsffi.objects).length;
        jsffi.objects[n] = jsval;
        return n;
    };
});

EM_JS(JsRef, jsffi_string, (const char *ptr), {
    return jsffi.to_jsref(UTF8ToString(ptr));
});

EM_JS(JsRef, jsffi_i32, (int32_t x), {
    return jsffi.to_jsref(x);
});

EM_JS(JsRef, jsffi_wrap_func, (em_callback_func cfunc), {
    return jsffi.to_jsref(wasmTable.get(cfunc));
});

EM_JS(JsRef, jsffi_call_method_1, (JsRef c_target, const char *c_name, JsRef c_arg0), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let arg0 = jsffi.from_jsref(c_arg0);
    let res = target[name].call(target, arg0);
    return jsffi.to_jsref(res);
});

EM_JS(JsRef, jsffi_getattr, (JsRef c_target, const char *c_name), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let res = target[name];
    return jsffi.to_jsref(res);
});

EM_JS(void, jsffi_setattr, (JsRef c_target, const char *c_name, JsRef c_val), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let val = jsffi.from_jsref(c_val);
    target[name] = val;
});
