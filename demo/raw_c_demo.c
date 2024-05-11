#include <stdio.h>
#include <emscripten.h>
#include "spy.h"

extern JsRef jsffi_GLOBALTHIS;
extern JsRef jsffi_CONSOLE;

EMSCRIPTEN_KEEPALIVE
void onclick() {
    printf("onclick!\n");
}

EM_JS(JsRef, jsffi_wrap_func, (em_callback_func cfunc), {
    let func = () => {
        dynCall("v", cfunc);
    };
    return jsffi.to_jsref(func);
});

EMSCRIPTEN_KEEPALIVE
int main(void) {
  jsffi_init();
  JsRef js_msg = jsffi_string("hello from c 2");
  jsffi_call_method_1(
      jsffi_CONSOLE,
      "log",
      js_msg);

  JsRef js_document = jsffi_getattr(
      jsffi_GLOBALTHIS,
      "document"
  );

  JsRef js_title = jsffi_call_method_1(
      js_document,
      "getElementById",
      jsffi_string("title")
  );

  jsffi_setattr(
      js_title,
      "innerText",
      jsffi_string("hello HTML from C")
  );

  JsRef js_btn = jsffi_call_method_1(
      js_document,
      "getElementById",
      jsffi_string("btn")
  );

  JsRef js_onclick = jsffi_wrap_func(&onclick);

  jsffi_call_method_1(
      jsffi_CONSOLE,
      "log",
      js_onclick
  );

  jsffi_setattr(
      js_btn,
      "onclick",
      js_onclick
  );

  //jsffi_call_method_1(jsffi_CONSOLE, "log", js_div);

  return 0;
}
