"""
CLI helper that prints compiler flags for building out-of-tree modules
against libspy.

Usage:
    python -m spy.build.flags --cflags --target=wasi --build-type=debug
    python -m spy.build.flags --ldflags --target=wasi --build-type=release
    python -m spy.build.flags --libdir --target=wasi --build-type=debug
    python -m spy.build.flags --cc --target=wasi
"""

import argparse
import sys
from typing import Optional

import spy.libspy

BuildType = str  # "release" | "debug"

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

_TARGET_LDFLAGS: dict[str, list[str]] = {
    "wasi": [
        "--target=wasm32-wasi-musl",
    ],
    "emscripten": [],
    "native": [],
    "native-static": [
        "--target=native-native-musl",
        "-static",
    ],
}

_BUILD_TYPE_CFLAGS: dict[str, list[str]] = {
    "release": ["-DSPY_RELEASE", "-O3", "-flto"],
    "debug": ["-DSPY_DEBUG", "-O0", "-g"],
}

_BUILD_TYPE_LDFLAGS: dict[str, list[str]] = {
    "release": ["-flto"],
    "debug": [],
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


def _check_target(target: str) -> None:
    if target not in _TARGET_CFLAGS:
        raise ValueError(f"Unknown target: {target!r}. Valid: {list(_TARGET_CFLAGS)}")


def _check_build_type(build_type: str) -> None:
    if build_type not in _BUILD_TYPE_CFLAGS:
        raise ValueError(
            f"Unknown build_type: {build_type!r}. Valid: {list(_BUILD_TYPE_CFLAGS)}"
        )


def get_cflags(target: str, build_type: BuildType) -> list[str]:
    _check_target(target)
    _check_build_type(build_type)
    include = ["-I", str(spy.libspy.INCLUDE)]
    return (
        _BASE_CFLAGS + _TARGET_CFLAGS[target] + _BUILD_TYPE_CFLAGS[build_type] + include
    )


def get_ldflags(target: str, build_type: BuildType) -> list[str]:
    _check_target(target)
    _check_build_type(build_type)
    return _TARGET_LDFLAGS[target] + _BUILD_TYPE_LDFLAGS[build_type]


def get_libdir(target: str, build_type: BuildType) -> str:
    _check_target(target)
    _check_build_type(build_type)
    return str(spy.libspy.BUILD.join(target, build_type))


def get_cc(target: str) -> str:
    _check_target(target)
    return _TARGET_CC[target]


def get_ar(target: str) -> str:
    _check_target(target)
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
        "--build-type",
        choices=list(_BUILD_TYPE_CFLAGS),
        default="debug",
        help="Build type (default: debug)",
    )
    parser.add_argument(
        "--cflags",
        action="store_true",
        help="Print CFLAGS (requires --target)",
    )
    parser.add_argument(
        "--ldflags",
        action="store_true",
        help="Print LDFLAGS (requires --target)",
    )
    parser.add_argument(
        "--libdir",
        action="store_true",
        help="Print the libspy build directory (-L path, requires --target)",
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
        parts += get_cflags(args.target, args.build_type)

    if args.ldflags:
        if not args.target:
            print("error: --ldflags requires --target", file=sys.stderr)
            sys.exit(1)
        parts += get_ldflags(args.target, args.build_type)

    if args.libdir:
        if not args.target:
            print("error: --libdir requires --target", file=sys.stderr)
            sys.exit(1)
        parts.append(f"-L{get_libdir(args.target, args.build_type)}")

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
