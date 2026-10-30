---
title: Contributing
---

# Contributing to SPy

Thanks for helping improve SPy! There are many ways to contribute: trying SPy
and reporting issues, improving the documentation, adding tests or examples,
and working on the compiler itself.

## Talk to us

  - [Discord server](https://discord.gg/wRb29FGZpP)
  - Monthly community call, on the first Wednesday of the month at 17:30 CET
    ([Google calendar](https://calendar.app.google/5qMsCibGVH8kAkcs7)).
  - [Issues and pull requests](https://github.com/spylang/spy) on GitHub.
  - The [roadmap](https://github.com/spylang/spy/blob/main/ROADMAP.md) lists
    what we plan to work on.

## Contributing code

The contribution workflow (fork, branch, pre-commit hooks, pull request) is
described in
[CONTRIBUTING.md](https://github.com/spylang/spy/blob/main/CONTRIBUTING.md).

### Development setup

SPy needs Python dependencies (managed by pip, uv or Pixi) and a native
library, [bdw-gc](https://www.hboehm.info/gc/). The most up-to-date
requirements are in the
[tests workflow](https://github.com/spylang/spy/blob/main/.github/workflows/tests.yml).
Run all the commands below from the root of the repository, without an active
virtual environment.

=== "uv"
    Prerequisite: bdw-gc (`libgc-dev` on Debian/Ubuntu).

    ```bash
    uv sync
    . .venv/bin/activate
    make -C spy/libspy
    ```
=== "pip"
    Prerequisites: Python 3.12, pip >= 25.1 (for PEP 735 dependency groups) and
    bdw-gc (`libgc-dev` on Debian/Ubuntu).

    ```bash
    python3 -m venv .venv
    . .venv/bin/activate
    pip install -e . --group dev
    make -C spy/libspy
    ```
=== "Pixi"
    No prerequisite: [Pixi](https://pixi.sh) also installs bdw-gc.

    ```bash
    pixi run make-libspy
    pixi shell
    ```

    Other useful commands: `pixi run ruff-format`, `pixi run ruff-check`,
    `pixi run doc-serve`, `pixi run test-xdist`.

### Optional build dependencies

`spy build` compiles the generated C code to a native or WebAssembly binary.
Depending on the target:

  - **Native** (`--target native`): a system C compiler such as `gcc` or
    `clang` (`build-essential` on Debian/Ubuntu).
  - **Emscripten** (`--target emscripten`): the
    [Emscripten SDK](https://github.com/emscripten-core/emsdk), with the
    `latest` toolchain activated so that `emcc` is on your `PATH`.
  - **WASI** (`--target wasi`): uses [Zig](https://ziglang.org/), which is
    installed automatically with SPy.

The interpreter and `redshift` work without any of these.

### Running the tests

```bash
pytest
pytest -n auto -v -x
```

To understand how the compiler is organized, read
[The compilation pipeline](../explanation/compilation-pipeline.md).

## Contributing to the documentation

See [Contributing to the documentation](docs.md).
