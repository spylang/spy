#include <emscripten.h>

typedef struct {
    int id;
} JsRef;

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

EM_JS(void, jsffi_call_method_1, (JsRef c_target, const char *c_name, JsRef c_arg0), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let arg0 = jsffi.from_jsref(c_arg0);
    target[name].call(target, arg0);
});


/* EM_JS(void, call_alert, (), { */
/*   console.log("hello world"); */
/* }); */

int main() {
  jsffi_init();
  JsRef js_console = {1};
  JsRef js_msg = jsffi_string("hello from c");
  jsffi_call_method_1(js_console, "log", js_msg);
  return 0;
}
