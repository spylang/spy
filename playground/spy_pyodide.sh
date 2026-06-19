#!/bin/sh

# Wrapper around spy_pyodide.mjs: run spy EXACTLY like the web playground, but
# from the command line (CDN Pyodide + the release libspy shipped in
# playground/).
#
# Requires the playground to be built first (see Makefile: `make local`) so that
# playground/libspy.{mjs,wasm} and playground/spylang-*.whl exist.
#
#     ./spy_pyodide.sh ../examples/1_high_level/hello.spy
#     ./spy_pyodide.sh redshift ../examples/1_high_level/hello.spy

HERE=$(dirname "$0")
exec node "$HERE/spy_pyodide.mjs" "$@"
