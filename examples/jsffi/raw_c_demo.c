#include <stdio.h>
#include <emscripten.h>
#include "spy.h"

EMSCRIPTEN_KEEPALIVE
void onclick() {
    printf("onclick!\n");
}


EMSCRIPTEN_KEEPALIVE
int main(void) {
  jsffi_init();
  JsRef jsffi_GLOBALTHIS = spy_jsffi$get_GlobalThis();
  JsRef jsffi_CONSOLE = spy_jsffi$get_Console();

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
