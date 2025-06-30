# SPy

**Discord server**&nbsp;&nbsp;&nbsp;[![](https://dcbadge.limes.pink/api/server/https://discord.gg/wRb29FGZpP)](https://discord.gg/wRb29FGZpP)


## What is SPy?

TL;DR: SPy is a subset/variant of Python specifically designed to be
statically compilable **while** retaining a lot of the "useful" dynamic parts
of Python.

It consists of:

  1. an interpreter (so that you can have the usual nice "development
     experience" that you have in Python)

  2. a compiler (for speed)

The documentation is very scarce at the moment, but the best source to
understand the ideas behind SPy are probably the talks which [Antonio Cuni](https://github.com/antocuni/) gave:

  - at [PyCon Italy 2025](https://antocuni.eu/2025/05/31/spy--pycon-it-2025/)

  - at PyCon US 2024: [slides](https://antocuni.pyscriptapps.com/spy-pycon-2024/latest/) and [recording](https://www.youtube.com/watch?v=hnQ0oJ_yXlw&ab_channel=PyConUS).


Additional info can be found on:

  - Antonio Cuni's [blog](http://antocuni.eu/tags/#tag:spy)
  - [A peek into a possible future of Python in the browser](https://lukasz.langa.pl/f37aa97a-9ea3-4aeb-b6a0-9daeea5a7505/) by Łukasz Langa.


## Local development setup

At the moment, the only supported installation method for SPy is by doing an
"editable install" of the Git repo checkout.

The most up-to-date version of the requirements and the installation steps is the [GitHub action workflow](https://github.com/spylang/spy/blob/main/.github/workflows/tests.yml).

Prerequisites:

  - Python 3.12

Installation:

  1. Install the `spy` package in editable mode:
      ```
      $ cd /path/to/spy/
      $ pip install -e .
      ```

  2. Build the `libspy` runtime library:
     ```
     $ make -C spy/libspy
     ```

Run the test suite:

```
$ pytest
```

All the tests in `spy/tests/compiler/` are executed in three modes:

  - `interp`: run the SPy code via the interpreter
  - `doppler`: perform redshift, then run the redshifted code via the
    interpreter
  - `C`: generate C code, compile to WASM, then run it using `wasmtime`

## Basic usage examples

1. Execute a program in interpreted mode:
   ```
   $ spy examples/hello.spy
   Hello world!
   ```

2. Perform redshift and dump the generated source code:
   ```
   $ spy -r examples/hello.spy
    def main() -> void:
        print_str('Hello world!')
    ```

3. Perform redshift and THEN execute the code:
   ```
   $ spy -r -x examples/hello.spy
   Hello world!
   ```

4. Compile to executable:
   ```
   $ spy -c -t native examples/hello.spy
   $ ./examples/hello
   Hello world!
   ```

## Inspecting compilation pipeline

Moreover, there are more flags to stop the compilation pipeline and inspect
the result at each phase.

The full compilation pipeline is:

  - `pyparse`: source code -> generate Python AST
  - `parse`: Python AST -> SPy AST
  - `symtable`: Analyze the SPy AST and produce a symbol table for each scope
  - `redshift`: SPy AST -> redshifted SPy AST
  - `cwrite`: redshifted SPy AST -> C code
  - `compile`: C code -> executable

Each step has a corresponding command line option which stops the
compiler at that stage and dumps human-readable results.

Examples:

```
$ spy --pyparse examples/hello.spy
$ spy --parse examples/hello.spy
$ spy --symtable examples/hello.spy
$ spy --redshift examples/hello.spy
$ spy --cwrite examples/hello.spy
```

Moreover, the `execute` step performs the actual execution: it can happen
either after `symtable` (in "interp mode") or after `redshift` (in "doppler
mode").
