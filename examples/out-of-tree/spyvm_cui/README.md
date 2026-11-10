<ai>
# SPy bindings for CUI

An out-of-tree SPy builtin VM module that wraps [CUI][cui], a native immediate-mode
UI library written in C99. It runs both with the C backend (native executable) and
in interpreted mode (through `ctypes`).

This is a spike for demo purposes, not a complete binding: it exposes the subset of
CUI needed by `demo/counter.spy`.

[cui]: https://github.com/yappologistic/CUI

## How it works

CUI is an immediate-mode library: every frame the program calls components, which
return what happened (clicked, changed) and read or write the program's own state.
A CUI app looks like this:

```c
while (cui_app_frame(app)) {
    cui_ctx *ui = cui_app_ui(app);
    cui_column(ui, .pad = 24, .gap = 12) {
        if (cui_button(ui, "Save")) save();
        cui_switch(ui, "Notifications", &on);
    }
}
```

The C version relies on C pointers to the program's variables (`&on`) and on macros
that open and close a block (`cui_column(...) { ... }`). Neither exists in SPy, so
the glue in `src/spyvm_cui.c` hides them:

- Containers are split into explicit `*_begin` / `*_end` functions.
- Widget state lives in the glue, in small tables keyed by the widget label. For
  example `cui.switch(label, value)` returns the new value, so SPy writes
  `enabled = cui.switch("Enable", enabled)`.
- The app loop uses `cui_app_frame` (polling) instead of `cui_app_run`, so no
  callback is needed. This matters because SPy has no general callback support.

## Two ABIs

The same glue exposes two families of functions:

- `spy_cui$*`: the C-backend ABI. Strings are `spy_StrObject *`, so the C backend can
  call them directly.
- `pycui$*`: the `ctypes` ABI. Strings are plain `const char *`.

The interpreted backend cannot use the first family: a `spy_StrObject` lives in
libspy's WASM linear memory, and its address is meaningless to a native shared
library. So `__init__.py` builds the `ctypes` calls from the `pycui$*` symbols.
</ai>

## Build

CUI is not vendored. The Makefile fetches it into `vendor/CUI` on first use and
generates its single-file distribution:

```
make -C examples/out-of-tree/spyvm_cui          # native archives + ctypes .so
make -C examples/out-of-tree/spyvm_cui interp   # only the ctypes .so
```

This needs CMake's dependencies for the X11 backend: `libx11-dev` on Debian/Ubuntu.

## Run

<ai>
From `examples/out-of-tree/spyvm_cui/demo`. `spy.toml` loads the module.
</ai>

```
spy counter.spy                 # interpreted, through ctypes
spy build counter.spy           # native executable
./build/counter
```

<ai>
Any CUI app can save a screenshot and quit, which is useful for tests:
</ai>

```
CUI_SCREENSHOT=/tmp/shot.png CUI_SCREENSHOT_FRAMES=8 ./build/counter
```

## Not done

<ai>
- Only the native target is supported. CUI has no WASI build, so interpreted mode
  uses `ctypes` rather than a WASM bundle.
- WebAssembly: CUI can compile to WASM, but it needs `cui_app_run` with a callback
  and a different host page; this is not wired up.
- The binding covers the components used by the demo; adding more is mechanical
  (add a `core_*` function and the two exported wrappers).
</ai>
