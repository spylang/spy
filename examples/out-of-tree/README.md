# Out-of-tree builtin modules

This example demonstrates how to define and use an **out-of-tree builtin
VM module** in SPy: a builtin module that lives outside the main SPy
source tree, typically used to wrap an existing C library.

**THIS IS LIKELY A TEMPORARY FEATURE**. The long term plan is to have a different and
more direct way to write bindings to C libraries, but this is a good starting point for
now.

There are two modules, illustrating two different scenarios:

- **`spyvm_qrcodegen`** wraps
  [qrcodegen](https://www.nayuki.io/page/qr-code-generator-library) (by Project
  Nayuki, MIT licensed), a C library **vendored** into this repo. It has a WASM
  build, so it works both in interpreted mode and with the C backend. The demo
  `demo/qrgen.spy` prints a QR code to the terminal.

- **`spyvm_libmagic`** wraps the **system** [libmagic][] library (the engine
  behind the Unix `file` command), installed via the OS package manager. It has
  no WASM build, so it works *only* with the C backend (linking `-lmagic`); in
  interpreted mode its functions raise `NotImplementedError`. The demo
  `demo/read_magic.spy` works similarly to Unix `file` command.

[libmagic]: https://www.darwinsys.com/file/

## Vendored vs system libraries

The two modules illustrate the difference between wrapping a vendored library
and a system one:

| | `spyvm_qrcodegen` | `spyvm_libmagic` |
|---|---|---|
| Library source | vendored under `vendor/` | installed by the OS package manager |
| WASM build (`.a`) | yes (`wasi`, `emscripten`, …) | **no** |
| Works in interp mode | yes | **no** (raises `NotImplementedError`) |
| Works with the C backend | yes | yes, linking `-lmagic` |
| Linking | path to our `.a` | our glue `.a` **+** system `-lmagic` |

Because libmagic has no WASM build, the SPy interpreter cannot call into it: the
builtin functions raise `NotImplementedError`. The module is only useful with
the C backend, targeting `native`.

## Layout

```
out-of-tree/
├── vendor/qrcodegen/   # upstream C library, vendored.
├── spyvm_qrcodegen/    # out-of-tree module wrapping the vendored qrcodegen.
├── spyvm_libmagic/     # out-of-tree module wrapping the *system* libmagic.
│   ├── __init__.py     #   the ModuleRegistry: bindings + C-build metadata
│   ├── Makefile        #   builds the glue into build/<target>/spyvm_libmagic.a (native only)
│   └── src/
│       ├── spyvm_libmagic.c  # glue: SPy bytes -> magic_buffer() -> SPy str
│       └── spyvm_libmagic.h
└── demo/
    ├── spy.toml        # project manifest; lists out-of-tree modules to load.
    ├── qrgen.spy       # SPy program that imports `qrcodegen`.
    └── read_magic.spy  # SPy program that imports `magic`.
```

An out-of-tree builtin module is an importable Python package exposing a
`MODULE` instance of `ModuleRegistry`, with bindings and C-build metadata.

## Installing libmagic

```bash
apt install libmagic-dev      # Debian/Ubuntu
brew install libmagic         # macOS
```

## Building the extension modules

Each module has a Makefile that builds all the relevant targets:

```bash
make -C spyvm_qrcodegen   # , for all targets
make -C spyvm_libmagic    # build/native[-static]/<build-type>/spyvm_libmagic.a
```

The Makefiles produce artifacts like:

  - `build/native/debug/spyvm_qrcodegen.a`
  - `build/native/release/spyvm_qrcodegen.a`
  - `build/wasi/debug/spyvm_qrcodegen.a`
  - ...

More generally:
  - `build/<target>/<build-type>/spyvm_<modname>.a

Then SPy automatically selects the right archive to include in the build. The
interpreter loads the `wasi/debug` archive via wasmtime.

`spyvm_libmagic.a` is built only for the `native` target: this is intentional since
there is no WASM build of libmagic, and it's why the example works only after
compilation.

## Running the demos

The demos can be run either by relying on the project manifest (`spy.toml`)
or by passing the out-of-tree module explicitly on the command line:

```bash
# qrcodegen works in interpreted mode (it has a WASM build):
$ spy demo/qrgen.spy "https://github.com/spylang/spy"

# Equivalent, without using spy.toml:
$ spy --no-spy-toml --extra-vm-module ./spyvm_qrcodegen demo/qrgen.spy "hello"

# libmagic has no WASM build, so it works only with the C backend:
$ spy build demo/read_magic.spy
$ ./demo/build/read_magic /tmp/test.png
/tmp/test.png: PNG image data, 0 x 0, 0-bit grayscale, non-interlaced  [image/png]
```

CLI `--extra-vm-module` flags are additive on top of `spy.toml`.
