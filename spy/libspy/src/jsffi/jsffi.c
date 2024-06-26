#include <emscripten.h>
#include "spy.h"

/*
typedef struct {
    int id;
} JsRef;
*/

EM_JS(JsRef, jsffi_debug, (const char *ptr), {
    let s = UTF8ToString(ptr);
    console.log(s);
});


EM_JS(void, jsffi_init, (), {
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

JsRef jsffi_GLOBALTHIS = {0};
JsRef jsffi_CONSOLE = {1};

EMSCRIPTEN_KEEPALIVE
int foo() {
  jsffi_init();
  JsRef js_msg = jsffi_string("hello from c");
  jsffi_call_method_1(
      jsffi_CONSOLE,
      "log",
      js_msg);

  JsRef js_document = jsffi_getattr(
      jsffi_GLOBALTHIS,
      "document"
  );

  JsRef js_div = jsffi_call_method_1(
      js_document,
      "getElementById",
      jsffi_string("out")
  );

  jsffi_setattr(
      js_div,
      "innerText",
      jsffi_string("hello HTML from C")
  );

  //jsffi_call_method_1(jsffi_CONSOLE, "log", js_div);

  return 0;
}
