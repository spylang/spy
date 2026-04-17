# SPy roadmap

This is a very imprecise, possibly broken, probably outdated roadmap for SPy.

The reason it exists is to give a very rough idea of the past and future trajectory of
the project at the time of writing, but it can change at any time depending on the
findings and the needs.

**Last updated on 2026-04-17**.


The roadmap is divided into multiple pillars. Each pillar can be pursued more or less
independently of the others, although they are often interconnected. We intentionally
don't put an expected completion date.

The pillars are:

  - **core language**: features to make the SPy language more generally useful. A lot of
    the innovative stuff like redshifting and compile-time metaprogramming go here.

  - **stdlib**: libraries written in SPy itself; lives in `stdlib/*.spy`. Often these
    tasks depends on one or more "core language" features.

  - **Memory managment**: integration with refcounting and/or other GCs.

  - **SPy/C integration**: make it possible to seamlessly use C libraries from SPy programs.

  - **SPy/Python integration**: make it possible to seamlessly `import` python libraries
    in SPy, and SPy libraries in python.


## Core language

**Northern star**: have enough features to be able to write the SPy interpreter in SPy
itself.

Smaller goals: have enough features to:

  - implement advent of code problems;

  - write simple CLI tools;

  - write an efficient interpreter for a toy language.

### Q2/2026

- implement a `print()` with variable number of arguments (requires some kind of
  macro-like functionality)

- blue-time support for `*args` and `**kwargs`

- implement f-strings



### Done in Q1/2026

✅ `dict` literals: https://github.com/spylang/spy/issues/342

✅ support for CLI arguments: https://github.com/spylang/spy/issues/353

✅ support for preliminary file I/O: https://github.com/spylang/spy/pull/447

✅ compile-time friendly `tuple`: https://github.com/spylang/spy/pull/402

✅ implement `is` and `is not`: https://github.com/spylang/spy/pull/428

✅ PEP 695 syntax sugar for `@blue.generic` functions: https://github.com/spylang/spy/pull/437

✅ add support for default arguments: https://github.com/spylang/spy/pull/442

✅ `f32` and `complex` types: https://github.com/spylang/spy/pull/347 https://github.com/spylang/spy/pull/398


### Done in Q4/2025

✅ better debugging

  - ✅ SPy-level tracebacks

  - ✅ `breakpoint`

✅ `list` literals

### Done in Q3/2025

✅ better error messages (e.g. turn `AssertionErrror` into proper messages)

✅ better blue/red checks (e.g. raise an error if we call a blue function with red arguments)

✅ refactor `__dunder__` methods and introduce metafunctions

✅ blue-time descriptor protocol

✅ `for` loops, `range`, iterator protocol


### TODO: (loosely ordered by priority)

- enough metaprogramming capabilities to implement e.g. `dataclasses`

- serialization of the "live image" after redshifting

- support for heap-allocated `class`es

- support for `with` and context managers

- support for `try/catch` (currently all `raise` are turned into panics)


## stdlib

### Q2/2026

- write `str` and `bytes` in pure SPy


### DONE in Q1/2026

✅ preliminary `file` object: https://github.com/spylang/spy/pull/447

✅ improve standard builtin types:
  - add support for slices: https://github.com/spylang/spy/pull/345
  - add `str.replace`: https://github.com/spylang/spy/pull/394
  - https://github.com/spylang/spy/pull/460


### DONE in Q3/2025

✅ introduce the `stdlib` directory and add support for importing from there

✅ `stdlib/_list.spy`

✅ `stdlib/_dict.spy`

✅ `stdlib/array.spy`

### TODO

- preliminary `socket` support

- continue improving `list`, `dict` and other builtin types with the missing
  functionalities

- improve `array`, which is very limited and just a PoC by now

- more stdlib modules; the following is a non-exahustive list but gives an idea of what might be needed:

  - `datetime`

  - `argparse`

  - `json`

- full support for I/O, removing ad-hoc builtins and using a more general mechanism to
  call C libraries provided by SPy/C


## Memory management

### DONE in Q1/2026

✅ distinguish between `gc_alloc` and `raw_malloc: https://github.com/spylang/spy/pull/371 https://github.com/spylang/spy/pull/383

✅ introduce `gc_ref` and `raw_ref`

✅ Add support for Boehm GC https://github.com/spylang/spy/pull/383


### TODO

- distinguish between pointer-to-object, pointer-to-unbounded-array and
  pointer-to-bounded-array (similar to e.g. rust slices);

- add basic refcounting support. In pure-SPy configuration it will be basic refcounting
  without any cycle detection; when SPy/Python integration is enabled, it will map to
  `Py_IncRef/Py_DecRef` and rely on CPython's GC for cycle detection;

- experiment with [Whippet](https://github.com/wingo/whippet/)


## SPy/C integration

**Northern stars**: be able to implement `posix`, `socket`, and `sqlite` by wrapping C libraries

Requirements/misc notes:

  - "CFFI for SPy" (which is VERY different than "use CFFI to create CPython bindings")

  - generic way to interface with external C libraries

  - need to work both in the interpreter and in the compiler

  - unclear how it works with WASM-centric interpreter

  - related work: [Zig's `@cImport`](https://zighelp.org/chapter-4/#cimport)

### Q2/2026

- start to experiment with it


## SPy/Python integration


### Low-level bindings via cffi

This is easy but limited: SPy code is translated to C, wrapped by `cffi` and then
imported into CPython. It works only one way and with very limited types (scalars and
arrays).  It's good enough to pass e.g. `numpy` arrays and doing unumerical computations
in SPy, though.

DONE in Q2/2025:

  - ✅ introduce the `py-cffi` output kind

TODO:

  - automatic conversion of `array.spy` types to and from CPython's `memoryview`/`np.array`


### Full feature bindings

This is the ultimate goal for SPy/Python integration, allowing seamless interop between
the two.

The plan is the following:

  - SPy programs can be compiled to standalone executable or CPython extension modules

  - when targeting CPython modules, SPy essentially becomes a "better Cython"

  - when targeting a standalone executable, SPy programs can opt-in for CPython
    compatibility


When CPython compatibility is *disabled*:

  - executables are self-contained

  - they can be statically linked

  - they don't require `libpython.so`

  - they can choose multiple memory management strategies (refcounting or other GCs)

When CPython compatibility is enabled:

  - the SPy program essentially becomes a CPython module

  - SPy can `import` arbitrary Python modules

  - the executable links to `libpython.so` and calls the `main` function in the SPy module

  - refconting is mandatory

The actual interop between SPy and Python will be implemented in pure SPy, by calling
the corresponding `Py*` functions exposed by `Python.h`.

This task requires:

  - `SPy/C` integration (to be able wrap and call `Python.h` from SPy)

  - refcounting memory model


## Documentation and tooling

### DONE in Q1/2026

✅ rework CLI using subcommands instead of flags: https://github.com/spylang/spy/pull/332

✅ docs skeleton and automation: https://github.com/spylang/spy/pull/349

✅ switch documentation to mkdocs-material: https://github.com/spylang/spy/pull/372

✅ HTML backend for AST visualization: https://github.com/spylang/spy/pull/413 https://github.com/spylang/spy/pull/414 https://github.com/spylang/spy/pull/424

✅ playground: share button and snippet links: https://github.com/spylang/spy/pull/427
