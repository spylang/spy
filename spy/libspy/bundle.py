"""
Link multiple .a archives into a single WASM reactor module.

This is the core of the out-of-tree module bundling strategy: instead of
loading multiple WASM modules at runtime, we link everything together
ahead of time with wasm-ld (via zig cc) so that llwasm still sees exactly
one module.
"""

from typing import Literal

import py.path

from spy.util import robust_run

# Targets that produce a WASM output from link_bundle
BundleTarget = Literal["wasi"]


def link_bundle(
    archives: list[py.path.local],
    exports: list[str],
    *,
    out: py.path.local,
) -> None:
    """
    Link one or more .a archives (wasm32-wasi-musl) into a single WASM
    reactor module.

    All archives are wrapped in --whole-archive so that symbols reachable
    only via WASM exports are not discarded by the linker.

    Args:
        archives: list of .a archive paths (libspy.a first, then extras)
        exports:  list of symbol names to expose as WASM exports
        out:      output .wasm path
    """
    cmdline = [
        "python",
        "-m",
        "ziglang",
        "cc",
        "--target=wasm32-wasi-musl",
        "-mexec-model=reactor",
        "-Wl,--whole-archive",
        *[str(a) for a in archives],
        "-Wl,--no-whole-archive",
        *[f"-Wl,--export={name}" for name in exports],
        "-o",
        str(out),
    ]
    robust_run(cmdline)
