#ifndef SPY_H
#define SPY_H

// POSIX.1-2008 is needed for clock_gettime, nanosleep, getline
// Must be defined before any system headers are included
#ifndef _POSIX_C_SOURCE
#  define _POSIX_C_SOURCE 200809L
#endif

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#if (defined(SPY_TARGET_WASI) + defined(SPY_TARGET_EMSCRIPTEN) +                       \
     defined(SPY_TARGET_NATIVE)) == 0
#  error "You must define one and exactly one of the SPY_TARGET_* macros"
#endif

#if defined(SPY_TARGET_NATIVE)
#  define WASM_EXPORT(name) name
#  define WASM_IMPORT(name) name
#else
#  define WASM_EXPORT(name) __attribute__((export_name(#name))) name
#  define WASM_IMPORT(name)                                                            \
      __attribute__((import_module("env"), import_name(#name))) name
#endif

#if defined(SPY_RELEASE) + defined(SPY_DEBUG) != 1
#  error "You must define either SPY_RELEASE or SPY_DEBUG"
#endif

#if defined(__GNUC__) || defined(__clang__)
#  define NORETURN __attribute__((noreturn))
#elif defined(_MSC_VER)
#  define NORETURN __declspec(noreturn)
#else
#  define NORETURN _Noreturn // C11
#endif

#include "spy/__spy__.h"
#include "spy/builtins.h"
#include "spy/debug.h"
#include "spy/gc.h"
#include "spy/math.h"
#include "spy/operator.h"
#include "spy/posix.h"
#include "spy/rawbuffer.h"
#include "spy/str.h"
#include "spy/time.h"
#include "spy/unsafe.h"

#ifdef SPY_TARGET_EMSCRIPTEN
#  include "spy/jsffi.h"
#endif

#ifdef SPY_HAS_AWS
#  include "spy/aws.h"
#endif

#endif /* SPY_H */
