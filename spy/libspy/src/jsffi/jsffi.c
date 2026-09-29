#include "spy.h"
#include <emscripten.h>

EM_JS_DEPS(jsffi, "$UTF8ToString,$wasmTable,$wasmMemory");

/*
 * EM_JS stringifies its body without macro expansion. Going through one more macro
 * level expands the macros used in the JS body first (e.g. JSVAL_F64), so the JS
 * code can share constants with the C code.
 *
 * Careful: every identifier of the body is expanded, including `true` and `false`
 * (macros from <stdbool.h>). So only use EM_JS_MACROS for bodies that need C macros
 * and do not contain such identifiers.
 */
#define EM_JS_MACROS(ret, name, args, body...) EM_JS(ret, name, args, body)

// see the corresponding comment in jsffi.h
void jsffi_force_include(void) {};

EM_JS(JsRef, jsffi_debug, (const char *ptr), {
    let s = UTF8ToString(ptr);
    console.log(s);
});

EM_JS(int32_t, jsffi_debug_n_jsrefs, (void), {
    // number of live (non-singleton) JsRefs, see jsffi.to_jsref / jsffi_drop_ref
    let n = jsffi.n_live;
    console.log("Number of live JsRef", n);
    return n;
});

EM_JS(void, jsffi_init_objects, (void), {
    let jsffi = {
        objects: {},
        next_id: 7,  // 0-6 are reserved for well-known singletons
        n_live: 0    // number of live JsRefs with id >= 7
    };
    globalThis.jsffi = jsffi;
    jsffi.objects[0] = globalThis;
    jsffi.objects[1] = console;
    jsffi.objects[2] = globalThis.document;
    jsffi.objects[3] = undefined;
    jsffi.objects[4] = null;
    jsffi.objects[5] = true;
    jsffi.objects[6] = false;

    jsffi.from_jsref = function(idval) {
        let obj = jsffi.objects[idval];
        if (idval >= 7 && (obj === undefined || obj === null)) {
            console.error(`jsffi internal error: Undefined id ${ idval }`);
            throw new Error(`Undefined id ${ idval }`);
        }
        return obj;
    };

    jsffi.to_jsref = function(jsval) {
        if (jsval === undefined) return 3;
        if (jsval === null)      return 4;
        if (jsval === true)      return 5;
        if (jsval === false)     return 6;
        let id = jsffi.next_id++;
        // console.log(`to_jsref, jsval: ${ jsval }`);
        jsffi.objects[id] = jsval;
        jsffi.n_live++;
        return id;
    };
});

EM_JS_MACROS(void, jsffi_init_from_jsval, (void), {
    jsffi.from_jsval = function(tag, val) {
        switch(tag) {
            case JSVAL_JSREF:   return jsffi.from_jsref(val);
            case JSVAL_F64:
            case JSVAL_I32:     return val;
            case JSVAL_STR:     return UTF8ToString(val);
            case JSVAL_BOOL:    return !!val;
            case JSVAL_FUNCPTR: return wasmTable.get(val);
        }
    };
});

void jsffi_init(void) {
    jsffi_init_objects();
    jsffi_init_from_jsval();
}

EM_JS(JsRef, jsffi_string, (const char *ptr), { return jsffi.to_jsref(UTF8ToString(ptr)); });

EM_JS(JsRef, jsffi_i32, (int32_t x), { return jsffi.to_jsref(x); });

EM_JS(JsRef, jsffi_f64, (double x), { return jsffi.to_jsref(x); });

EM_JS(void, jsffi_drop_ref, (JsRef c_ref), {
    // Singletons (ids 0-6) are never dropped.
    let obj = jsffi.objects[c_ref];
    if (c_ref >= 7 && obj !== undefined && obj !== null) {
        jsffi.objects[c_ref] = null;
        jsffi.n_live--;
    }
});

EM_JS(JsRef, jsffi_getattr, (JsRef c_target, const char *c_name), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let res = target[name];
    return jsffi.to_jsref(res);
});

EM_JS(void, jsffi_setattr, (JsRef c_target, const char *c_name,
                             int32_t tag, double val), {
    let target = jsffi.from_jsref(c_target);
    target[UTF8ToString(c_name)] = jsffi.from_jsval(tag, val);
});


EM_JS(JsRef, jsffi_u8array_from_ptr, (void *ptr, int32_t length), {
    let view = new Uint8ClampedArray(wasmMemory.buffer, ptr, length);
    return jsffi.to_jsref(view);
});

EM_JS(JsRef, jsffi_new_ImageData, (JsRef ref_array, int32_t width, int32_t height), {
    let array = jsffi.from_jsref(ref_array);
    return jsffi.to_jsref(new ImageData(array, width, height));
});

EM_JS(int32_t, jsffi_to_i32, (JsRef c_ref), {
    return jsffi.from_jsref(c_ref)|0;
});

EM_JS(double, jsffi_to_f64, (JsRef c_ref), {
    return +jsffi.from_jsref(c_ref);
});

EM_JS(void, jsffi_request_animation_frame, (em_callback_func cfunc), {
    requestAnimationFrame(wasmTable.get(cfunc));
});

/*
 * jsffi_call_method.c is included so that all EM_JS
 * functions share the same translation unit and can access the `jsffi`
 * object initialised by jsffi_init().
 */
#include "jsffi_call_method.c"
