# spy
SPy language


## Local development setup

At the moment, the only supported installation method for SPy is by doing an
"editable install" of the git repo checkout.

The most up to date version of the requirements and the installation steps is the [Github action workflow](https://github.com/spylang/spy/blob/main/.github/workflows/tests.yml).

Prerequisites:

  - Python 3.12

  - [wasi-sdk](https://github.com/WebAssembly/wasi-sdk): this is used by some
    tests to check that we can compile to WASM using `wasi-sdk`. Currently,
    **the test suite expects that `clang` points to
    `/path/to/wask-sdk/bin/clang`** (PRs to improve the situation are
    welcome).

  - `unbuffer` (`apt install expect`), which is used to force gcc to emit
    colored error messages

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
  - `C`: generate C code, compile to WASM, then run it using `wasmtime`.

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
  - `symtable`: Analize the SPy AST and produce a symbol table for each scope
  - `redshift`: SPy AST -> redshifted SPy AST
  - `cwrite`: redshifted SPy AST -> C code
  - `compile`: C code -> executable

Each of this step has a corresponding command line option which stops the
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
