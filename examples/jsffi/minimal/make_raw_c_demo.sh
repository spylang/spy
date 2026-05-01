#!/usr/bin/env bash

# Based on: https://stackoverflow.com/a/246128
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

set -e


LIBSPY="${SCRIPT_DIR}/../../spy/libspy/"

CFLAGS="
  $1
  -D SPY_DEBUG
  -D SPY_TARGET_EMSCRIPTEN
  -I ${LIBSPY}/include/
  -L ${LIBSPY}/build/emscripten/debug
  -lspy
"


mkdir -p build
emcc $CFLAGS raw_c_demo.c -o build/raw_c_demo.js
