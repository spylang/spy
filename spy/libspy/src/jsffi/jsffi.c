#include <emscripten.h>
#include "spy.h"

/*
typedef struct {
    int id;
} JsRef;
*/

JsRef jsffi_GLOBALTHIS = {0};
JsRef jsffi_CONSOLE = {1};

JsRef spy_jsffi$get_GlobalThis(void) {
    return jsffi_GLOBALTHIS;
}

JsRef spy_jsffi$get_Console(void) {
    return jsffi_CONSOLE;
}

EM_JS(JsRef, _jsffi_debug, (const char *ptr), {
    let s = UTF8ToString(ptr);
    console.log(s);
});

void spy_jsffi$debug(spy_Str *s) {
    _jsffi_debug(s->utf8);
}


EM_JS(void, spy_jsffi$init, (void), {
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

EM_JS(JsRef, _jsffi_string, (const char *ptr), {
    return jsffi.to_jsref(UTF8ToString(ptr));
});

JsRef spy_jsffi$js_string(spy_Str *s) {
    return _jsffi_string(s->utf8);
}

EM_JS(JsRef, _jsffi_call_method_1, (JsRef c_target, const char *c_name, JsRef c_arg0), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let arg0 = jsffi.from_jsref(c_arg0);
    let res = target[name].call(target, arg0);
    return jsffi.to_jsref(res);
});

JsRef spy_jsffi$js_call_method_1(JsRef target, spy_Str *name, JsRef arg0) {
    return _jsffi_call_method_1(target, name->utf8, arg0);
}

EM_JS(JsRef, jsffi_getattr, (JsRef c_target, const char *c_name), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let res = target[name];
    return jsffi.to_jsref(res);
});

JsRef spy_jsffi$js_getattr(JsRef target, spy_Str *name) {
    return jsffi_getattr(target, name->utf8);
}

EM_JS(void, jsffi_setattr, (JsRef c_target, const char *c_name, JsRef c_val), {
    let target = jsffi.from_jsref(c_target);
    let name = UTF8ToString(c_name);
    let val = jsffi.from_jsref(c_val);
    target[name] = val;
});


EMSCRIPTEN_KEEPALIVE
int foo() {
  spy_jsffi$init();
  JsRef js_msg = _jsffi_string("hello from c");
  _jsffi_call_method_1(
      jsffi_CONSOLE,
      "log",
      js_msg);

  JsRef js_document = jsffi_getattr(
      jsffi_GLOBALTHIS,
      "document"
  );

  JsRef js_div = _jsffi_call_method_1(
      js_document,
      "getElementById",
      _jsffi_string("out")
  );

  jsffi_setattr(
      js_div,
      "innerText",
      _jsffi_string("hello HTML from C")
  );

  //_jsffi_call_method_1(jsffi_CONSOLE, "log", js_div);

  return 0;
}
