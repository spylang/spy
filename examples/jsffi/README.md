# SPy/emscripten example

This example shows:

  - how to compile spy code for emscripten

  - how to use the `jsffi` module to interact with the DOM

  - and how to call spy code from JS

**WARNING**: the `jsffi` module is just a proof of concept: it's incomplete, probably
buggy, and has the minimum amout of logic which is needed to run this demo, nothing
mode.

## How to compile and run

Compile `demo.spy` for emscripten:

```
❯ spy --compile --target emscripten demo.spy
[debug] build/demo.mjs
```

This generates various files in the `build` directory, including `demo.mjs` and
`demo.wasm`.

Then, start a local http server and open it in the browser:

```
❯ python -m http.server
Serving HTTP on 0.0.0.0 port 8000 (http://0.0.0.0:8000/) ...
127.0.0.1 - - [12/Nov/2025 00:33:52] "GET / HTTP/1.1" 304 -
127.0.0.1 - - [12/Nov/2025 00:33:52] "GET /build/demo.mjs HTTP/1.1" 200 -
127.0.0.1 - - [12/Nov/2025 00:33:53] "GET /build/demo.wasm HTTP/1.1" 200 -
```

## lldemo.spy and raw_c_demo.c

`lldemo.spy` shows how to call low-level JSFFI functions directly. It's not meant to be
useful, but to show how the high-level JSFFI operations are turned into low-level calls.

You can compile it with `spy --compile --target emscripten lldemo.spy`. To run it, edit
the file `index.html` and change the `<script>` tag.

`raw_c_demo.c` shows the same code but written directly in C.
