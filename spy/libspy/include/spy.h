#ifndef SPY_H
#define SPY_H

#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#if defined(SPY_TARGET_WASI) + defined(SPY_TARGET_EMSCRIPTEN) + defined(SPY_TARGET_NATIVE) == 0
#  error "You must define one and exactly one of the SPY_TARGET_* macros"
#endif


#if defined(SPY_TARGET_NATIVE)
#  define WASM_EXPORT(name) name
#  define WASM_IMPORT(name) name
# else
#  define WASM_EXPORT(name) \
    __attribute__((export_name(#name))) \
    name
#  define WASM_IMPORT(name) \
    __attribute__((import_module("env"), import_name(#name))) \
    name
#endif

#include "spy/builtins.h"
#include "spy/str.h"
#include "spy/gc.h"
#include "spy/rawbuffer.h"
#include "spy/debug.h"

#ifdef SPY_TARGET_EMSCRIPTEN
#include "spy/jsffi.h"
#endif

#endif /* SPY_H */
