---
title: Getting started
---

# Getting started

In this tutorial you install SPy, run your first program in the interpreter,
look at what the compiler does to it, and build a native executable.

/// note | Installation status
At the moment, the only supported way to install SPy is an editable install of
a Git checkout.
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

## Build an executable

```console
$ spy build examples/hello.spy --target native
$ ./examples/build/hello
Hello world!
```

`--target` also accepts `wasi` and `emscripten` to produce WebAssembly. These
targets have extra requirements, listed in the
[development setup](../contributing/index.md#development-setup).

## Where next?

  - Browse the [examples](../examples/1_high_level.md): they go from
    high-level code that looks like Python to low-level memory manipulation.
  - Try SPy without installing anything in the [playground](https://spylang.github.io/spy).
  - Look at how the compiler works in [The compilation pipeline](../explanation/compilation-pipeline.md).
