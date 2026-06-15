# Out-of-tree builtin modules

This example demonstrates how to define and use an **out-of-tree builtin
VM module** in SPy: a builtin module that lives outside the main SPy
source tree, typically used to wrap an existing C library.

**THIS IS LIKELY A TEMPORARY FEATURE**. The long term plan is to have a different and
more direct way to write bindings to C libraries, but this is a good starting point for
now.

The example wraps [qrcodegen](https://www.nayuki.io/page/qr-code-generator-library)
(by Project Nayuki, MIT licensed) and uses it to print a QR code to the
terminal.

## Layout

```
out-of-tree/
├── vendor/qrcodegen/   # upstream C library, vendored. In a real-world
│                       # setup this would typically be installed via the
│                       # system package manager.
├── spyvm_qrcodegen/    # the out-of-tree SPy builtin module: an importable
│                       # Python package exposing a `MODULE` instance of
│                       # ModuleRegistry, with bindings and C-build metadata.
└── demo/
    ├── spy.toml        # project manifest; lists out-of-tree modules to load.
    └── main.spy        # the SPy program that imports `qrcodegen`.
```

## Building the C library

```bash
cd vendor/qrcodegen
make TARGET=native     # produces build/native/libqrcodegen.a
make TARGET=wasi       # produces build/wasi/libqrcodegen.a
```

## Running the demo

The demo can be run either by relying on the project manifest (`spy.toml`)
or by passing the out-of-tree module explicitly on the command line:

```bash
# Reads demo/spy.toml, which lists ../spyvm_qrcodegen.
spy demo/main.spy

# Equivalent, without using spy.toml:
spy --no-spy-toml --extra-vm-module ./spyvm_qrcodegen demo/main.spy
```

CLI `--extra-vm-module` flags are additive on top of `spy.toml`.
