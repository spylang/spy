"""
Simple script to run WASI programs using wasmtime.

Similar in spirit to the `wasmtime` executable, with the advantage that
requires only `pip install wasmtime`, no extra dependency.

Mostly useful for tests.
"""

import argparse
import sys

import wasmtime as wt


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a WASI-enabled WebAssembly module using wasmtime."
    )
    parser.add_argument("wasm_file", help="Path to the .wasm file to run")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments to pass to the WASM program")

    args = parser.parse_args()

    # Set up WASI configuration
    store = wt.Store()
    wasi_config = wt.WasiConfig()
    wasi_config.argv = [args.wasm_file] + args.args
    wasi_config.inherit_stdout()
    wasi_config.inherit_stderr()
    wasi_config.inherit_stdin()
    store.set_wasi(wasi_config)

    # Load and instantiate the module
    module = wt.Module.from_file(store.engine, args.wasm_file)
    linker = wt.Linker(store.engine)
    linker.define_wasi()

    instance = linker.instantiate(store, module)

    # Run the `_start` function
    try:
        start = instance.exports(store)["_start"]
        assert isinstance(start, wt.Func)
        start(store)
    except wt.WasmtimeError as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
