---
title: Getting started
---

# Getting started

In this tutorial you install SPy, run your first program in the interpreter,
build a native executable, and look at what the compiler does to your program.

/// note | Installation status
At the moment, the only supported way to install SPy is an editable install of
a Git checkout. Installing with `uv tool install spylang --prerelease allow`
will soon be supported.
///

## Install SPy

You need [uv](https://docs.astral.sh/uv/), a C compiler (e.g. `build-essential`
on Debian/Ubuntu) and the [bdw-gc](https://www.hboehm.info/gc/) garbage
collector (`libgc-dev` on Debian/Ubuntu, `brew install bdw-gc` on macOS).

```bash
git clone https://github.com/spylang/spy
cd spy
uv sync
. .venv/bin/activate
make -C spy/libspy
```

`make -C spy/libspy` builds `libspy`, the small C runtime library that every
SPy program is linked against.

/// note
The `make -C spy/libspy` step will soon not be needed anymore.
///

For the other installation methods (pip, Pixi) and the optional build
dependencies, see the [development setup](../contributing/index.md#development-setup).

## Run a program in the interpreter

The repository contains `examples/hello.spy`:

```python
def main() -> None:
    print("Hello world!")
```

Every SPy program defines a `main` function: it is the entry point. Run it with
the interpreter, exactly as you would run a Python script:

```console
$ spy examples/hello.spy
Hello world!
```

## Build an executable

```console
$ spy build examples/hello.spy
[debug] examples/build/hello
$ ./examples/build/hello
Hello world!
```

The default target is `native`: `spy build examples/hello.spy` is the same as
`spy build --target native examples/hello.spy`. It only needs a C compiler.

Two options are worth knowing from the start:

  - `--release` builds an optimized executable (`-O3`, link-time optimization)
    without the debug checks. Without it, you get a debug build (`-O0 -g`),
    which is faster to compile.
  - `--static` produces a statically linked executable, which does not depend
    on shared libraries (native target only, not supported on macOS).

```console
$ spy build --release --static examples/hello.spy
[release] examples/build/hello
```

/// admonition | Debug and release modes

The two modes differ in more than compiler flags. In debug mode, a pointer
also stores the length of the memory it points to (such a pointer is often
called a *fat pointer*). This lets every indexing operation check that the
index is in range, and raise an `IndexError` if it is not. In release mode,
pointers are plain addresses and these checks are removed: an out-of-range
index silently reads or writes the wrong memory.

The performance difference between the two modes is huge. Use the debug build
while developing, and the release build for benchmarks and final executables.

///

`--target` also accepts `wasi` and `emscripten` to produce WebAssembly. `wasi`
works out of the box, but `emscripten` needs the
[Emscripten SDK](https://github.com/emscripten-core/emsdk) (`emcc`), see the
[development setup](../contributing/index.md#development-setup).

## See what the compiler does

Before generating code, the compiler *redshifts* the program: it runs all the
parts that can be computed ahead of time and keeps only what must happen at
run time. Ask for the result with `spy redshift`:

```console
$ spy redshift examples/hello.spy
def main() -> None:
    `_print::println[str]`('Hello world!')
```

The call to `print` has been resolved to a specialized, statically known
function, `println[str]`. Use `-x` to also execute the redshifted program:

```console
$ spy redshift -x examples/hello.spy
Hello world!
```

The other compilation phases (see
[The compilation pipeline](../explanation/compilation-pipeline.md)) can be
inspected the same way, with commands like `spy parse`, `spy scopes` or
`spy build --no-compile`.

## Where next?

  - Browse the [examples](../examples/1_high_level.md): they go from
    high-level code that looks like Python to low-level memory manipulation.
  - Try SPy without installing anything in the [playground](https://spylang.github.io/spy).
  - Look at how the compiler works in [The compilation pipeline](../explanation/compilation-pipeline.md).
