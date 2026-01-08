# SPy roadmap

This is a very imprecise, possibly broken, probably outdated roadmap for SPy.

The reason it exists is to give a very rough idea of the past and future trajectory of
the project at the time of writing, but it can change at any time depending on the
findings and the needs.

**Last updated on 2025-01-08**.


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


Done in Q3/2025:

  - ✅ better error messages (e.g. turn `AssertionErrror` into proper messages)

  - ✅ better blue/red checks (e.g. raise an error if we call a blue function with red arguments)

  - ✅ refactor `__dunder__` methods and introduce metafunctions

  - ✅ blue-time descriptor protocol

  - ✅ `for` loops, `range`, iterator protocol

Done in Q4/2025:

  - ✅ better debugging

    - ✅ SPy-level tracebacks

    - ✅ `breakpoint`

  - ✅ `list` literals


TODO: (loosely ordered by priority):

  - `dict` literals: https://github.com/spylang/spy/issues/342

  - support for CLI arguments: https://github.com/spylang/spy/issues/353

  - support for preliminary file I/O: https://github.com/spylang/spy/issues/354

  - compile-time friendly `tuple`

  - blue-time support for `*args` and `**kwargs`

  - implement a `print()` with variable number of arguments (requires some kind of
    macro-like functionality)

  - implement f-strings

  - enough metaprogramming capabilities to implement e.g. `dataclasses`

  - serialization of the "live image" after redshifting

  - support for heap-allocated `class`es

  - support for `with` and context managers

  - support for `try/catch` (currently all `raise` are turned into panics)


## stdlib

DONE in Q3/2025:

  - ✅ introduce the `stdlib` directory and add support for importing from there

  - ✅ `stdlib/_list.spy`

  - ✅ `stdlib/_dict.spy`

  - ✅ `stdlib/array.spy`


TODO:

  - preliminary I/O modules, using ad-hoc builtins

    - (part of) `os`

    - (part of) `io` / `file`

    - (part of) `socket`

  - improve `list` and `dict` with the missing functionalities

  - improve `array`, which is very limited and just a PoC by now

  - more stdlib modules; the following is a non-exahustive list but gives an idea of what might be needed:

    - `datetime`

    - `argparse`

    - `json`

  - full support for I/O, removing ad-hoc builtins and using a more general mechanism to
    call C libraries provided by SPy/C


## Memory management

Currently SPy doesn't have any GC and it just leaks memory.

TODO:

  - improve the `unsafe` module; currently we just have `gc_alloc` and `ptr`; we want:

    - distinguish between `gc_alloc` and `malloc/free`;

    - distinguish between pointer-to-object, pointer-to-unbounded-array and
      pointer-to-bounded-array (similar to e.g. rust slices);

    - introduce the concept of "reference", similarly to what `cffi` does. This is
      needed mostly to read nested struct fields;

  - add basic refcounting support. In pure-SPy configuration it will be basic
    refcounting without any cycle detection; when SPy/Python integration is enabled, it
    will map to `Py_IncRef/Py_DecRef` and rely on CPython's GC for cycle detection;

  - use the boehm GC: this is easy when compiling to native C, but it's non
    trivial for WASM targets, because we cannot easily walk the stack;

  - experiment with [Whippet](https://github.com/wingo/whippet/)



## SPy/C integration

**Northern stars**: be able to implement `posix`, `socket`, and `sqlite` by wrapping C libraries

Requirements/misc notes:

  - "CFFI for SPy" (which is VERY different than "use CFFI to create CPython bindings")

  - generic way to interface with external C libraries

  - need to work both in the interpreter and in the compiler

  - unclear how it works with WASM-centric interpreter

  - related work: [Zig's `@cImport`](https://zighelp.org/chapter-4/#cimport)



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
