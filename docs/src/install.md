---
title: Install
hide:
  - navigation
---

# Install SPy

/// note | Installation status
At the moment, the only supported way to install SPy is an editable install of
a Git checkout. Installing from a wheel, for example with
`uv tool install spylang --prerelease allow`, will soon be supported.
///

This page presents how to do this editable install with
[uv](https://docs.astral.sh/uv/).

## Prerequisites

You need:

  - [uv](https://docs.astral.sh/uv/getting-started/installation/), which also
    takes care of installing Python.
  - A C compiler: `build-essential` on Debian/Ubuntu, or the Xcode command line
    tools on macOS (`xcode-select --install`).
  - The [bdw-gc](https://www.hboehm.info/gc/) garbage collector (the
    Boehm-Demers-Weiser GC), which is not installed by uv:

    === "Debian/Ubuntu"

        ```bash
        sudo apt install libgc-dev
        ```

    === "macOS"

        With [Homebrew](https://brew.sh/):

        ```bash
        brew install bdw-gc
        ```

## Install from a Git checkout

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

## Check the installation

```console
$ spy examples/hello.spy
Hello world!
```

You are ready for the [Getting started tutorial](tutorials/getting-started.md).

For the other installation methods (pip, Pixi) and the optional build
dependencies, see the
[development setup](contributing/index.md#development-setup).
