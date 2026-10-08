#include <stdio.h>
#include <emscripten.h>
#include "spy.h"

static spy_Str str_log           = {3,  0, "log"};
static spy_Str str_getElementById = {14, 0, "getElementById"};
static spy_Str str_title         = {5,  0, "title"};
static spy_Str str_btn           = {3,  0, "btn"};
static spy_Str str_innerText     = {9,  0, "innerText"};
static spy_Str str_onclick       = {7,  0, "onclick"};
static spy_Str str_hello_c       = {14, 0, "hello from c 2"};
static spy_Str str_hello_html    = {18, 0, "hello HTML from C"};
static spy_Str str_document      = {8,  0, "document"};

EMSCRIPTEN_KEEPALIVE
void onclick() {
    spy_jsffi$js_call_method_1(
        spy_jsffi$get_Console(), &str_log,
        spy_jsffi$jsval_from_str(&str_onclick));
}

EMSCRIPTEN_KEEPALIVE
int main(void) {
    jsffi_init();
    JsRef console     = spy_jsffi$get_Console();
    JsRef globalThis  = spy_jsffi$get_GlobalThis();

    // console.log("hello from c 2")
    spy_jsffi$js_call_method_1(
        console, &str_log,
        spy_jsffi$jsval_from_str(&str_hello_c));

    // document = globalThis.document
    JsRef document = spy_jsffi$JsRef$__getattribute__(globalThis, &str_document);

    // title = document.getElementById("title")
    JsRef title = spy_jsffi$js_call_method_1(
        document, &str_getElementById,
        spy_jsffi$jsval_from_str(&str_title));

    // title.innerText = "hello HTML from C"
    spy_jsffi$JsRef$__setattr__(
        title, &str_innerText,
        spy_jsffi$jsval_from_str(&str_hello_html));

    // btn = document.getElementById("btn")
    JsRef btn = spy_jsffi$js_call_method_1(
        document, &str_getElementById,
        spy_jsffi$jsval_from_str(&str_btn));

    // btn.onclick = onclick
    spy_jsffi$JsRef$__setattr__(
        btn, &str_onclick,
        spy_jsffi$jsval_from_func(onclick));

    return 0;
}
