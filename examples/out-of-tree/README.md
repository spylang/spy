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

- **`spyvm_libmagic`** wraps the **system** `libmagic` library (the engine
  behind the Unix `file` command), installed via the OS package manager. It has
  no WASM build, so it works *only* with the C backend (linking `-lmagic`); in
  interpreted mode its functions raise `NotImplementedError`. The demo
  `demo/read_magic.spy` identifies a few file signatures. See
  `spyvm_libmagic/README.md` for details.

## Layout

```
out-of-tree/
├── vendor/qrcodegen/   # upstream C library, vendored.
├── spyvm_qrcodegen/    # out-of-tree module wrapping the vendored qrcodegen.
├── spyvm_libmagic/     # out-of-tree module wrapping the *system* libmagic.
│                       # An out-of-tree builtin module is an importable Python
│                       # package exposing a `MODULE` instance of
│                       # ModuleRegistry, with bindings and C-build metadata.
└── demo/
    ├── spy.toml        # project manifest; lists out-of-tree modules to load.
    ├── qrgen.spy       # SPy program that imports `qrcodegen`.
    └── read_magic.spy  # SPy program that imports `magic`.
```

## Building the C libraries

For qrcodegen (vendored), build both the upstream library and the glue:

```bash
make -C vendor/qrcodegen TARGET=native   # build/native/libqrcodegen.a
make -C vendor/qrcodegen TARGET=wasi      # build/wasi/libqrcodegen.a
make -C spyvm_qrcodegen  TARGET=native
make -C spyvm_qrcodegen  TARGET=wasi
```

For libmagic (system library), only the glue is built, and only natively
(there is no WASM build of libmagic):

```bash
make -C spyvm_libmagic TARGET=native     # build/native/libmagic_spy.a
```

## Running the demos

The demos can be run either by relying on the project manifest (`spy.toml`)
or by passing the out-of-tree module explicitly on the command line:

```bash
# qrcodegen works in interpreted mode (it has a WASM build):
spy demo/qrgen.spy "https://github.com/spylang/spy"

# Equivalent, without using spy.toml:
spy --no-spy-toml --extra-vm-module ./spyvm_qrcodegen demo/qrgen.spy "hello"

# libmagic has no WASM build, so it works only with the C backend:
spy build -x demo/read_magic.spy
```

CLI `--extra-vm-module` flags are additive on top of `spy.toml`.
