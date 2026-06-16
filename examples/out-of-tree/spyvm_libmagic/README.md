# spyvm_libmagic

An out-of-tree SPy builtin module wrapping the **system** [libmagic][] library
(the engine behind the Unix `file` command).

It is the companion of `spyvm_qrcodegen`, but illustrates a different scenario:
wrapping a library that is **installed on the system** rather than vendored.

[libmagic]: https://www.darwinsys.com/file/

## What's different from `spyvm_qrcodegen`

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

## Installing libmagic

```bash
apt install libmagic-dev      # Debian/Ubuntu
brew install libmagic         # macOS
```

## Layout

```
spyvm_libmagic/
├── __init__.py     # the ModuleRegistry: bindings + C-build metadata
├── Makefile        # builds our glue into build/<target>/spyvm_libmagic.a (native only)
└── src/
    ├── spyvm_libmagic.c  # glue: SPy bytes -> magic_buffer() -> SPy str
    └── spyvm_libmagic.h
```

## Building the glue

```bash
make TARGET=native          # produces build/native/spyvm_libmagic.a
```

There is intentionally no `wasi`/`emscripten` target.

## API

```python
import magic

magic.describe(data: bytes) -> str   # like `file`:            "PNG image data, ..."
magic.mime(data: bytes) -> str       # like `file --mime-type`: "image/png"
```

See `../demo/read_magic.spy` for a runnable example.
