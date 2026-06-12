"""
CLI helper that prints compiler flags for building out-of-tree modules
against libspy.

Usage:
    python -m spy.libspy.flags --cflags --target=wasi
    python -m spy.libspy.flags --include
    python -m spy.libspy.flags --cc --target=wasi
"""

import argparse
import sys
from typing import Optional

import spy.libspy

# Base CFLAGS shared by all targets (mirrors spy/libspy/Makefile)
_BASE_CFLAGS: list[str] = [
    "-fvisibility=hidden",
    "-fPIC",
]

# WASM-specific CFLAGS shared by wasi and emscripten
_WASM_CFLAGS: list[str] = [
    "-mmultivalue",
    "-Xclang",
    "-target-abi",
    "-Xclang",
    "experimental-mv",
    "-mbulk-memory",
]

_TARGET_CFLAGS: dict[str, list[str]] = {
    "wasi": [
        "-DSPY_TARGET_WASI",
        "--target=wasm32-wasi-musl",
        *_WASM_CFLAGS,
    ],
    "emscripten": [
        "-DSPY_TARGET_EMSCRIPTEN",
        *_WASM_CFLAGS,
    ],
    "native": [
        "-DSPY_TARGET_NATIVE",
    ],
    "native-static": [
        "-DSPY_TARGET_NATIVE",
        "--target=native-native-musl",
    ],
}

_TARGET_CC: dict[str, str] = {
    "wasi": "python -m ziglang cc",
    "emscripten": "emcc",
    "native": "cc",
    "native-static": "python -m ziglang cc",
}

_TARGET_AR: dict[str, str] = {
    "wasi": "python -m ziglang ar",
    "emscripten": "emar",
    "native": "ar",
    "native-static": "python -m ziglang ar",
}


def get_cflags(target: str) -> list[str]:
    if target not in _TARGET_CFLAGS:
        raise ValueError(f"Unknown target: {target!r}. Valid: {list(_TARGET_CFLAGS)}")
    return _BASE_CFLAGS + _TARGET_CFLAGS[target]


def get_include() -> str:
    return str(spy.libspy.INCLUDE)


def get_cc(target: str) -> str:
    if target not in _TARGET_CC:
        raise ValueError(f"Unknown target: {target!r}. Valid: {list(_TARGET_CC)}")
    return _TARGET_CC[target]


def get_ar(target: str) -> str:
    if target not in _TARGET_AR:
        raise ValueError(f"Unknown target: {target!r}. Valid: {list(_TARGET_AR)}")
    return _TARGET_AR[target]


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Print compiler flags for building out-of-tree libspy modules"
    )
    parser.add_argument(
        "--target",
        choices=list(_TARGET_CFLAGS),
        help="Build target",
    )
    parser.add_argument(
        "--cflags",
        action="store_true",
        help="Print CFLAGS (requires --target)",
    )
    parser.add_argument(
        "--include",
        action="store_true",
        help="Print the libspy include directory (-I path)",
    )
    parser.add_argument(
        "--cc",
        action="store_true",
        help="Print the C compiler for the given target (requires --target)",
    )
    parser.add_argument(
        "--ar",
        action="store_true",
        help="Print the archiver for the given target (requires --target)",
    )
    args = parser.parse_args(argv)

    parts: list[str] = []

    if args.cflags:
        if not args.target:
            print("error: --cflags requires --target", file=sys.stderr)
            sys.exit(1)
        parts += get_cflags(args.target)

    if args.include:
        parts.append(f"-I{get_include()}")

    if args.cc:
        if not args.target:
            print("error: --cc requires --target", file=sys.stderr)
            sys.exit(1)
        parts.append(get_cc(args.target))

    if args.ar:
        if not args.target:
            print("error: --ar requires --target", file=sys.stderr)
            sys.exit(1)
        parts.append(get_ar(args.target))

    if parts:
        print(" ".join(parts))


if __name__ == "__main__":
    main()
