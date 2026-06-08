# SPy examples

The main examples are organized into four directories, ordered by complexity:

| Directory | Description |
|---|---|
| [`1_high_level/`](1_high_level/) | High-level SPy code that looks close to Python |
| [`2_blue/`](2_blue/) | Blue functions, metafunctions, and compile-time computation |
| [`3_low_level/`](3_low_level/) | Structs, pointers, and direct memory access via `unsafe` |
| [`4_advanced/`](4_advanced/) | Advanced features and patterns |

Other directories contain more specialized examples:

| Directory | Description |
|---|---|
| [`cffi/`](cffi/) | Calling C libraries via CFFI |
| [`jsffi/`](jsffi/) | JavaScript FFI for WebAssembly targets |
| [`debugger/`](debugger/) | Using the SPy debugger (`spdb`) |
| [`multifile/`](multifile/) | Multi-file SPy projects |
| [`errors/`](errors/) | Examples of error handling and error messages |
| [`gc_stress/`](gc_stress/) | Garbage collector |

## Running the examples

```bash
spy 1_high_level/hello.spy
```

## For SPy developers

Examples in the four numbered directories are tested automatically. Run all of
them with:

```bash
pytest -x
```

To run and update the expected output for a single example:

```bash
pytest test_examples.py::test_example[collections] --update-examples
```

The `--update-examples` flag runs the example with `spy` and writes (or
overwrites) the corresponding file in `expected_output/`. Lines starting with
`# ` are stripped from the output before saving, so examples can print volatile
annotations (e.g. timings) without causing spurious test failures.
