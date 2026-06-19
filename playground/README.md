# SPy playground

The examples .spy files are in ../examples.

The Makefile can be used to build the playground locally. You first need to install the
[Emscripten SDK (emsdk)](https://github.com/emscripten-core/emsdk) and
[install/activate "lastest"](https://github.com/emscripten-core/emsdk#downloads--how-do-i-get-the-latest-emscripten-build)
so that the Emscripten Compiler Frontend (`emcc`) is available.

See also .github/workflows/playground-deploy.yml.

## Running spy on top of pyodide from the CLI

`spy_pyodide.sh` (a thin wrapper around `spy_pyodide.mjs`) runs SPy inside pyodide
inside `node`. It aims to be a headless version of the environment used by the
playground in the browser.

Pyodide is downloaded from the jsDelivr CDN, `spylang` is installed from
`playground/spylang-*.whl`, and libspy from `playground/libspy.{mjs,wasm}`.

You must build the playground first (`make local`) so that the wheel and
`libspy.{mjs,wasm}` exist. Then:

```
$ ./spy_pyodide.sh ../examples/1_high_level/hello.spy
$ ./spy_pyodide.sh redshift ../examples/1_high_level/hello.spy
```

The Pyodide runtime is cached under `playground/.pyodide-cache/` after the first
run; delete that directory to force a re-download.
